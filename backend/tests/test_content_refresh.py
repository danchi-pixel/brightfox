"""Exercise new files/versions through real APIs with scratch families; no AI or real data."""
import json

import pytest

from app.config import load_settings, settings
from app.content import registry
from .conftest import make_family


def write_topic(root, slug, name, tid):
    path = root / 'families' / slug / 'topics' / f'{tid}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    topic = {'id': tid, 'version': 1, 'format': 2, 'subject': 'other', 'grade': 4,
             'title': f'{name} new activity', 'intro': 'Vadi.', 'for': [name],
             'study': {'goals': [{'id': 'goal', 'text': 'Znam.'}],
                       'sections': [{'title': 'Novo', 'text': 'Razlaga.'}],
                       'cards': [{'front': 'Ena?', 'back': '1'}]},
             'tasks': [{'id': 'one', 'level': 1, 'kind': 'number', 'prompt': 'Ena?',
                        'answer': 1, 'solution': '1'}]}
    path.write_text(json.dumps(topic), encoding='utf-8')
    return path, topic


def test_new_files_versions_mocks_refresh_and_progress(client, tmp_path, monkeypatch):
    family = make_family('auto-content', ['Alan', 'Erik'])
    other = make_family('auto-other', ['Alan'])
    monkeypatch.setattr(settings, 'local_family', family.slug)
    source = registry.FileContentSource(tmp_path)
    previous = registry._source
    registry.set_source(source)
    try:
        alan, erik = family.learners['Alan'], family.learners['Erik']
        a, e = family.kids['Alan'], family.kids['Erik']
        def home(kid, lid):
            r = kid.get(f'/api/learners/{lid}/home')
            assert r.status_code == 200, r.text
            return r.json()['topics']
        assert home(a, alan) == []
        path, topic = write_topic(tmp_path, family.slug, 'Alan', 'alan-new')
        assert [t['id'] for t in home(a, alan)] == ['alan-new']
        assert home(e, erik) == []
        assert e.get(f'/api/learners/{erik}/topics/alan-new').status_code == 404
        assert other.admin.get('/api/studio/topics/alan-new').status_code == 404
        assert a.put(f'/api/learners/{alan}/topics/alan-new/progress', json={'known':['1'],'goals':['goal']}).status_code == 200
        assert a.post(f'/api/learners/{alan}/topics/alan-new/runs', json={'results':{'one':{'first':True,'tries':1}},'finished':True}).status_code == 201
        write_topic(tmp_path, family.slug, 'Erik', 'erik-new')
        assert [t['id'] for t in home(e, erik)] == ['erik-new']
        assert [t['id'] for t in home(a, alan)] == ['alan-new']
        topic.update(version=2, title='Updated music lesson')
        path.write_text(json.dumps(topic), encoding='utf-8')
        for _ in range(2):  # ordinary repeated browser requests, same server and source instance
            card = home(a, alan)[0]
            assert card['version'] == 2 and card['title'] == 'Updated music lesson'
            assert card['runs'] == 1 and card['study_state']['known'] == ['1']
            assert card['study_state']['ticked'] == ['goal']
        mock_dir = path.parent.parent / 'mocks'
        mock_dir.mkdir()
        mock = {'id':'alan-mock', 'version':1, 'subject':'other','grade':4,'title':'New mock',
                'intro':'Vadi.', 'for':['Alan'], 'minutes':5, 'topics':['alan-new'],
                'sections':[{'title':'A','tasks':[{'id':'m-one','topic':'alan-new','kind':'number',
                    'prompt':'Ena?', 'answer':1, 'solution':'1', 'points':1}]}]}
        mp = mock_dir / 'alan-mock.json'
        mp.write_text(json.dumps(mock), encoding='utf-8')
        assert [m['id'] for m in a.get(f'/api/learners/{alan}/mocks').json()] == ['alan-mock']
        assert e.get(f'/api/learners/{erik}/mocks').json() == []
        mock['for']=['Erik']; mock['version']=2
        mp.write_text(json.dumps(mock), encoding='utf-8')
        assert [m['version'] for m in e.get(f'/api/learners/{erik}/mocks').json()] == [2]
        assert a.get(f'/api/learners/{alan}/mocks').json() == []
        mp.unlink()  # scratch file only
        # Malformed edits must not silently keep serving an older snapshot, and repair self-recovers.
        path.write_text('{', encoding='utf-8')
        assert a.get(f'/api/learners/{alan}/home').status_code == 503
        path.write_text(json.dumps(topic), encoding='utf-8')
        assert home(a, alan)[0]['version'] == 2
        # Turn local mode off: the original production approval gate still applies.
        monkeypatch.setattr(settings, 'local_family', None)
        assert home(a, alan) == []
        assert family.admin.put('/api/studio/topics/alan-new/access', json={'version':2,'learner_ids':[alan]}).status_code == 200
        assert len(home(a, alan)) == 1
        topic['version']=3; path.write_text(json.dumps(topic), encoding='utf-8')
        assert home(a, alan) == []
    finally:
        registry.set_source(previous)


def test_registry_add_remove_and_cache(tmp_path):
    source = registry.FileContentSource(tmp_path)
    empty = source.content()
    assert source.content() is empty
    path, _ = write_topic(tmp_path, 'new-family', 'Alan', 'new-id')
    assert 'new-id' in source.content().topics
    path.unlink()
    assert source.content().topics == {}


@pytest.mark.parametrize('name,value', [('UCILNICA_API_HOST','0.0.0.0'), ('UCILNICA_BEHIND_PROXY','1'),
    ('UCILNICA_COOKIE_SECURE','1'), ('UCILNICA_STATIC_DIR','dist')])
def test_local_mode_refuses_production_configuration(monkeypatch, name, value):
    monkeypatch.setenv('UCILNICA_LOCAL_FAMILY','danijel')
    monkeypatch.setenv(name,value)
    with pytest.raises(ValueError, match='loopback'):
        load_settings()
