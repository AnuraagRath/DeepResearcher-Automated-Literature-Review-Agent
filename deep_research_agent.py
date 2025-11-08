import os
import re
import json
import time
import html
import textwrap
import pathlib
import argparse
import datetime
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
from urllib.parse import urlencode
from difflib import SequenceMatcher

# Load configuration
load_dotenv(dotenv_path=pathlib.Path(__file__).with_name('.env'))

OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gpt-oss:120b-cloud')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'https://ollama.com')
OLLAMA_CHAT_URL = os.getenv('OLLAMA_CHAT_URL', f'{OLLAMA_BASE_URL}/api/chat')
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')
PUBMED_EMAIL = os.getenv('PUBMED_EMAIL', 'noreply@example.com')

DEBUG = False

def _debug(msg: str) -> None:
    if DEBUG:
        print('[DEBUG]', msg)


# ------------------------ utility helpers -------------------------------

def _norm_title(t: str) -> str:
    """Normalize title for fuzzy deduplication."""
    t = re.sub(r"\s+", " ", t or "").strip().lower()
    t = re.sub(r"[^a-z0-9 ]+", '', t)
    return t


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ------------------------ Source: CrossRef --------------------------------

def crossref_search(query: str, max_results: int = 5) -> List[Dict]:
    _debug(f"CrossRef query → {query!r}")
    url = 'https://api.crossref.org/works'
    params = {
        'query.title': query,
        'rows': max_results,
        'sort': 'relevance'
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get('message', {}).get('items', [])
    out = []
    for item in items:
        title = (item.get('title') or [''])[0]
        authors = []
        for a in item.get('author', []):
            name = ' '.join(p for p in [a.get('given'), a.get('family')] if p)
            if name:
                authors.append(name)
        doi = item.get('DOI')
        abstract = item.get('abstract') or ''
        url = item.get('URL')
        year = None
        if item.get('published-print') and item['published-print'].get('date-parts'):
            year = item['published-print']['date-parts'][0][0]
        elif item.get('published-online') and item['published-online'].get('date-parts'):
            year = item['published-online']['date-parts'][0][0]
        out.append({
            'title': html.unescape(title),
            'authors': authors,
            'abstract': re.sub('<[^<]+?>', '', abstract) if abstract else '',
            'doi': doi,
            'url': url,
            'year': year,
            'source': 'CrossRef'
        })
    _debug(f"CrossRef returned {len(out)} items")
    return out


# ------------------------ Source: OpenAlex --------------------------------

def openalex_search(query: str, max_results: int = 5) -> List[Dict]:
    """Search OpenAlex for research papers (no API key required)."""
    _debug(f"OpenAlex query → {query!r}")
    url = "https://api.openalex.org/works"
    params = {"search": query, "per-page": max_results}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = []

    for item in data.get("results", []):
        title = item.get("title", "Untitled")
        authors = [a["author"]["display_name"] for a in item.get("authorships", []) if "author" in a]
        year = item.get("publication_year", "")
        doi = item.get("doi")
        url_paper = item.get("id", "")
        abstract = item.get("abstract_inverted_index", {})

        # Safely rebuild abstract text if numeric keys exist
        if isinstance(abstract, dict):
            valid_tokens = [(int(k), v) for k, v in abstract.items() if k.isdigit()]
            if valid_tokens:
                tokens = sorted(valid_tokens, key=lambda x: x[0])
                abstract_text = " ".join(v for _, v in tokens)
            else:
                # fallback if keys aren't numeric (new OpenAlex style)
                abstract_text = " ".join(abstract.keys())
        else:
            abstract_text = ""

        results.append(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "url": url_paper,
                "abstract": abstract_text.strip(),
            }
        )

    _debug(f"OpenAlex returned {len(results)} papers")
    return results



# ------------------------ Source: PubMed (NCBI E-utilities) ----------------

def pubmed_search(query: str, max_results: int = 5) -> List[Dict]:
    _debug(f"PubMed query → {query!r}")
    base_esearch = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    esearch_params = {
        'db': 'pubmed',
        'term': query,
        'retmax': max_results,
        'retmode': 'json',
        'email': PUBMED_EMAIL
    }
    r = requests.get(base_esearch, params=esearch_params, timeout=20)
    r.raise_for_status()
    ids = r.json().get('esearchresult', {}).get('idlist', [])
    out = []
    if not ids:
        return out
    # efetch for summaries
    efetch = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    efetch_params = {
        'db': 'pubmed',
        'id': ','.join(ids),
        'retmode': 'xml',
        'email': PUBMED_EMAIL
    }
    r2 = requests.get(efetch, params=efetch_params, timeout=30)
    r2.raise_for_status()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(r2.text)
    for article in root.findall('.//PubmedArticle'):
        try:
            art_title = article.find('.//ArticleTitle').text or ''
            abstract_nodes = article.findall('.//AbstractText')
            abstract = ' '.join(a.text or '' for a in abstract_nodes)
            authors = []
            for au in article.findall('.//Author'):
                last = au.find('LastName')
                giv = au.find('ForeName')
                if last is not None and giv is not None:
                    authors.append(f"{giv.text} {last.text}")
            doi = None
            for eid in article.findall('.//ArticleId'):
                if eid.attrib.get('IdType') == 'doi':
                    doi = eid.text
            pmid = article.find('.//PMID').text
            url = f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'
            out.append({
                'title': html.unescape(art_title),
                'authors': authors,
                'abstract': html.unescape(abstract),
                'doi': doi,
                'url': url,
                'year': None,
                'source': 'PubMed'
            })
        except Exception:
            continue
    _debug(f"PubMed returned {len(out)} items")
    return out


# ------------------------ Source: Google Scholar via SerpAPI or scholarly --

def serpapi_scholar_search(query: str, max_results: int = 5) -> List[Dict]:
    if not SERPAPI_API_KEY:
        return []
    _debug(f"SerpAPI Google Scholar query → {query!r}")
    url = 'https://serpapi.com/search'
    params = {
        'engine': 'google_scholar',
        'q': query,
        'api_key': SERPAPI_API_KEY,
        'num': max_results
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    out = []
    for item in data.get('organic_results', [])[:max_results]:
        title = item.get('title')
        snippet = item.get('snippet')
        link = item.get('link')
        authors = []
        out.append({
            'title': html.unescape(title or ''),
            'authors': authors,
            'abstract': html.unescape(snippet or ''),
            'doi': None,
            'url': link,
            'year': None,
            'source': 'GoogleScholar'
        })
    _debug(f"SerpAPI Scholar returned {len(out)} items")
    return out


def scholarly_fallback_search(query: str, max_results: int = 5) -> List[Dict]:
    try:
        from scholarly import scholarly
    except Exception:
        return []
    _debug(f"scholarly fallback query → {query!r}")
    gen = scholarly.search_pubs(query)
    out = []
    for i, item in enumerate(gen):
        if i >= max_results:
            break
        try:
            pub = scholarly.fill(item)
            title = pub.get('bib', {}).get('title')
            authors = pub.get('bib', {}).get('author', '').split(' and ')
            abstract = pub.get('bib', {}).get('abstract', '')
            url = pub.get('pub_url') or pub.get('bib', {}).get('url')
            out.append({
                'title': html.unescape(title or ''),
                'authors': authors,
                'abstract': html.unescape(abstract or ''),
                'doi': None,
                'url': url,
                'year': None,
                'source': 'GoogleScholar'
            })
        except Exception:
            continue
    _debug(f"scholarly fallback returned {len(out)} items")
    return out


# ------------------------ Original arXiv + web search + Ollama -------------
# (Keep the original arxiv_search + web_search + chat_ollama but adapt names)

def arxiv_search(query: str, max_results: int = 5) -> List[Dict]:
    _debug(f"arXiv query → {query!r}")
    base = 'http://export.arxiv.org/api/query'
    params = {
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': max_results,
    }
    resp = requests.get(base, params=params, timeout=30)
    resp.raise_for_status()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(resp.text)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    papers: List[Dict] = []

    for entry in root.findall('atom:entry', ns):
        title = html.unescape(entry.find('atom:title', ns).text.strip())
        summary = html.unescape(entry.find('atom:summary', ns).text.strip())
        published = entry.find('atom:published', ns).text[:10]
        authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
        pdf_url = ''
        for link in entry.findall('atom:link', ns):
            if link.attrib.get('type') == 'application/pdf':
                pdf_url = link.attrib['href']
                break
        papers.append({
            'title': title,
            'authors': authors,
            'abstract': summary,
            'doi': None,
            'url': pdf_url or entry.find('atom:id', ns).text,
            'year': published,
            'source': 'arXiv'
        })
    _debug(f"arXiv returned {len(papers)} papers")
    return papers


def web_search_ollama(query: str, max_results: int = 5) -> List[Dict]:
    _debug(f"Ollama web_search query → {query!r}")
    url = f"{OLLAMA_BASE_URL}/api/web_search"
    headers = {'Authorization': f'Bearer {OLLAMA_API_KEY}', 'Content-Type': 'application/json'}
    payload = {'query': query, 'max_results': max_results}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get('results', [])
        out = []
        for r in results:
            out.append({
                'title': r.get('title'),
                'authors': [],
                'abstract': r.get('content') or r.get('snippet') or '',
                'doi': None,
                'url': r.get('url'),
                'year': None,
                'source': 'Web'
            })
        _debug(f"Ollama web_search returned {len(out)} results")
        return out
    except Exception as exc:
        _debug(f"web_search failed: {exc}")
        return []


def chat_ollama(system_prompt: str, user_prompt: str) -> str:
    _debug('Calling Ollama chat endpoint')
    payload = {
        'model': OLLAMA_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'stream': False,
    }
    headers = {
        'Authorization': f'Bearer {OLLAMA_API_KEY}',
        'Content-Type': 'application/json',
    }
    resp = requests.post(OLLAMA_CHAT_URL, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if 'message' in data:
        content = data['message']['content']
    elif 'choices' in data:
        content = data['choices'][0]['message']['content']
    else:
        raise RuntimeError('Unexpected Ollama response format')
    _debug(f"LLM returned {len(content)} characters")
    return content


# ------------------------ Consolidation / dedupe --------------------------

def consolidate_results(lists: List[List[Dict]], similarity_threshold: float = 0.85) -> List[Dict]:
    """Flatten, deduplicate and score results from multiple sources.
    Deduplication uses DOI if available else fuzzy title similarity.
    """
    all_items: List[Dict] = [item for sub in lists for item in sub]
    consolidated: List[Dict] = []

    for item in all_items:
        doi = (item.get('doi') or '').lower() if item.get('doi') else None
        title_norm = _norm_title(item.get('title', ''))
        found = False
        for c in consolidated:
            # match by DOI first
            if doi and c.get('doi') and doi == (c.get('doi') or '').lower():
                # merge
                c['sources'].add(item.get('source'))
                if not c.get('abstract') and item.get('abstract'):
                    c['abstract'] = item.get('abstract')
                found = True
                break
            # else fuzzy match titles
            if title_norm and _similar(title_norm, _norm_title(c.get('title', ''))) >= similarity_threshold:
                c['sources'].add(item.get('source'))
                if not c.get('abstract') and item.get('abstract'):
                    c['abstract'] = item.get('abstract')
                # prefer DOI if missing
                if not c.get('doi') and item.get('doi'):
                    c['doi'] = item.get('doi')
                found = True
                break
        if not found:
            new = item.copy()
            new['sources'] = set([item.get('source')])
            consolidated.append(new)
    # postprocess: convert source sets to sorted list and add a simple score
    for c in consolidated:
        sources = [s for s in c.get('sources', []) if isinstance(s, str) and s.strip()]
        c['sources'] = sorted(set(sources))
        # naive score: #sources + presence of doi
        c['score'] = len(c['sources']) + (1 if c.get('doi') else 0)
    # sort by score desc
    consolidated.sort(key=lambda x: x['score'], reverse=True)
    _debug(f"Consolidated to {len(consolidated)} unique items")
    return consolidated


# ------------------------ Markdown formatting ----------------------------

def mk_source_block(items: List[Dict]) -> str:
    lines = []
    for i, it in enumerate(items, 1):
        authors = ', '.join(it.get('authors') or [])
        doi = it.get('doi')
        url = it.get('url') or ''
        lines.append(f"**[{it.get('source')}-{i}]** [{it.get('title')}]({url})  \n_Authors_: {authors}  \n_Year_: {it.get('year')}\n\n{(it.get('abstract') or '')}\n")
    return '\n'.join(lines)


class DeepResearchAgentPlus:
    SYSTEM_PROMPT = textwrap.dedent(
        """
        You are a thorough, methodical research assistant that writes detailed
        markdown research reports by combining evidence from many scholarly
        and web sources. Always cite facts with source tags that appear in the
        supplied data (e.g. [SemanticScholar-1], [CrossRef-2], [PubMed-1], [OpenAlex-1], [GoogleScholar-1], [Web-1]).

        The report should include:
        1) Short background & motivation
        2) Key findings (with inline citations)
        3) Open questions / future directions
        4) A references section (markdown list)
        5) A "Sources & Summaries" table describing each source used
        """
    )

    def __init__(self, max_each: int = 5):
        self.max_each = max_each

    def research(self, query: str) -> str:
        # gather
        web = web_search_ollama(query, max_results=self.max_each)
        arxiv = arxiv_search(query, max_results=self.max_each)
        cross = crossref_search(query, max_results=self.max_each)
        openalex = openalex_search(query, max_results=self.max_each)
        pubmed = pubmed_search(query, max_results=self.max_each)
        # scholar: serpapi -> fallback to scholarly
        scholar = serpapi_scholar_search(query, max_results=self.max_each)
        if not scholar:
            scholar = scholarly_fallback_search(query, max_results=self.max_each)

        # consolidate
        consolidated = consolidate_results([web, arxiv, cross, openalex, pubmed, scholar])

        # prepare prompt sections for the LLM
        sections = {
            'Web': mk_source_block(web),
            'arXiv': mk_source_block(arxiv),
            'CrossRef': mk_source_block(cross),
            'OpenAlex': mk_source_block(openalex),
            'PubMed': mk_source_block(pubmed),
            'GoogleScholar': mk_source_block(scholar),
            'Consolidated': '\n'.join(
                f"**[Consolidated-{i}]** [{c.get('title', 'Untitled')}] — sources: {', '.join([s for s in c.get('sources', []) if s])}"
                for i, c in enumerate(consolidated, 1)
            )
        }

        user_prompt = textwrap.dedent(f"""
        Topic: **{query}**

        ### SOURCES - raw (by provider)
        Web results:
        {sections['Web']}

        arXiv results:
        {sections['arXiv']}

        CrossRef results:
        {sections['CrossRef']}

        OpenAlex results:
        {sections['OpenAlex']}

        PubMed results:
        {sections['PubMed']}

        Google Scholar results:
        {sections['GoogleScholar']}

        Consolidated unique papers:
        {sections['Consolidated']}

        Using the material above, write the markdown report now (background, key findings with citations, open questions, references, and a "Sources & Summaries" table).
        """
        )
        # call ollama
        return chat_ollama(self.SYSTEM_PROMPT, user_prompt)


# ------------------------ CLI entry point --------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='DeepResearchAgentPlus')
    parser.add_argument('query', help='research topic')
    parser.add_argument('--max', type=int, default=5, help='max results per source')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    if not OLLAMA_API_KEY:
        raise EnvironmentError('OLLAMA_API_KEY not found – create a .env file next to this script.')

    agent = DeepResearchAgentPlus(max_each=args.max)
    report = agent.research(args.query)

    print('\n--- MARKDOWN REPORT ------------------------------------------------\n')
    print(report)

    try:
        # safe filename
        slug = ''.join(c.lower() if c.isalnum() else '_' for c in args.query).strip('_')
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        out_dir = pathlib.Path('reports')
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{slug}_{timestamp}.md"
        path.write_text(report, encoding='utf-8')
        print(f"\n✅ Report saved to: {path}\n")
    except Exception as exc:
        print(f"\n⚠️  Could not write report file: {exc}\n")


if __name__ == '__main__':
    main()
