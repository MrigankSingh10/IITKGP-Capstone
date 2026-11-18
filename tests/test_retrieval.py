import numpy as np
import pytest
from tokenizers import Tokenizer

from hr_navigator.ingestion.pages import make_chunks
from hr_navigator.retrieval.embeddings import connect, embed_batches, read_vector
from hr_navigator.retrieval.search import search, validate_citation


def page(text, code='A', number=1):
    return {'page_id': f'sha:page_{number:04}', 'source_pdf_id': 'sha',
            'pdf_page_number': number, 'scope': 'statutory', 'labour_code': code,
            'category': 'Acts', 'original_title': 'Example act', 'source_url': 'https://example.org',
            'language_heuristic': 'Latin (heuristic)', 'extraction_status': 'extracted', 'text': text}


def test_chunks_remain_on_one_page_and_bounded():
    tokenizer = Tokenizer.from_file('configs/bge-small-en-v1.5-tokenizer.json')
    doc = page('Minimum wages and standards. ' * 500)
    chunks = list(make_chunks(doc, tokenizer, 200, 40))
    assert len(chunks) > 1
    assert all(c['page_id'] == doc['page_id'] and c['token_count'] <= 202 for c in chunks)
    assert all(c['text'] == doc['text'][c['char_start']:c['char_end']] for c in chunks)
    assert chunks[1]['char_start'] < chunks[0]['char_end']


def test_filtered_hybrid_and_citation_validation():
    a = {**page('wages notification and payment', 'A', 1), 'chunk_id': 'a'}
    b = {**page('wages notification and payment', 'B', 2), 'chunk_id': 'b'}
    c = {**page('wages rate', 'A', 1), 'chunk_id': 'c'}
    vectors = {'a': np.array([1., 0.]), 'b': np.array([1., 0.]), 'c': np.array([0., 1.])}
    result = search('wages notification', [a, b, c], vectors, [1, 0], labour_code='A')
    assert len(result) == 1 and result[0]['chunk_id'] == 'a'
    assert search('wages', [a, b], source_scope='company', mode='bm25') == []
    pages = {a['page_id']: a}
    assert validate_citation(a, pages)
    assert not validate_citation({**a, 'source_url': 'https://bad.example'}, pages)
    assert not validate_citation({**a, 'pdf_page_number': 3}, pages)


def test_embedding_cache_validates_and_deduplicates(tmp_path):
    class Config:
        model = 'test'
    class Client:
        config = Config()
        calls = 0
        def embed(self, inputs):
            self.calls += 1
            return {'data': [{'index': i, 'embedding': [0.1] * 384} for i in range(len(inputs))]}
    db = connect(tmp_path / 'cache.sqlite')
    client = Client()
    try:
        chunks = [{'text': 'short text'}, {'text': 'short text'}]
        embed_batches(client, chunks, db, 'configs/bge-small-en-v1.5-tokenizer.json', pause=0)
        embed_batches(client, chunks, db, 'configs/bge-small-en-v1.5-tokenizer.json', pause=0)
        assert client.calls == 1 and len(read_vector(db, 'test', 'short text')) == 384
        with pytest.raises(ValueError):
            embed_batches(client, chunks, db, 'configs/bge-small-en-v1.5-tokenizer.json', batch_size=17)
    finally:
        db.close()


def test_grounded_answer_rejects_fabricated_quote():
    import json
    from hr_navigator.retrieval.grounded import answer_with_evidence

    evidence = {**page('The date is notified by the Central Government.'), 'chunk_id': 'a'}
    class Client:
        def __init__(self, quote):
            self.quote = quote
        def chat(self, *args, **kwargs):
            return {'choices': [{'message': {'content': json.dumps({
                'answer': 'A notification is required.',
                'citations': [{'chunk_id': 'a', 'quote': self.quote}],
            })}}]}
    pages = {evidence['page_id']: evidence}
    assert answer_with_evidence(Client('invented text'), 'When?', [evidence], pages)['decision'] == 'escalate'
    good = answer_with_evidence(Client('Central Government'), 'When?', [evidence], pages)
    assert good['decision'] == 'escalate' and good['sources'][0]['page_number'] == 1
    assert 'A notification is required.' not in good['answer']


def test_date_filter_is_not_faked():
    with pytest.raises(ValueError, match='Date filtering unavailable'):
        search('test', [], mode='bm25', date_filter='2026-01-01')


def test_generated_quote_must_appear_on_original_page():
    import json
    from hr_navigator.retrieval.grounded import answer_with_evidence

    original = page('Original verified page text')
    fake = {**original, 'chunk_id': 'forged', 'text': 'Forged supporting passage'}
    class Client:
        def chat(self, *args, **kwargs):
            return {'choices': [{'message': {'content': json.dumps({
                'answer': 'False answer',
                'citations': [{'chunk_id': 'forged', 'quote': 'Forged supporting passage'}],
            })}}]}
    result = answer_with_evidence(Client(), 'Question?', [fake], {original['page_id']: original})
    assert result['decision'] == 'escalate' and result['sources'] == []
    assert not validate_citation({**original, 'pdf_page_number': '1'}, {original['page_id']: original})
    assert not validate_citation({**original, 'original_title': 'Forged title'}, {original['page_id']: original})
