import json
import zipfile
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.local_setup import prepare
from app.models import Family, Learner, PracticeRun, TopicProgress, User
from app.models.base import Base


def test_local_setup_backs_up_and_preserves_profiles_and_history(tmp_path):
    cfg = Settings(data_dir=tmp_path, local_family='danijel')
    cfg.ensure_dirs()
    engine = create_engine(f'sqlite:///{cfg.db_path.as_posix()}')
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        demo = Family(slug='test', name='Test family'); real = Family(slug='danijel',name='Existing household')
        db.add_all([demo,real]); db.flush()
        tina = Learner(family_id=demo.id,name='Tina')
        alan = Learner(family_id=real.id,name='Alan',grade=4,interests='music',tutor_daily_limit=9)
        erik = Learner(family_id=real.id,name='Erik',grade=6,color='#123456')
        db.add_all([tina,alan,erik]); db.flush()
        parent = User(family_id=demo.id,username='scratch-parent',password_hash='not-a-login',role='admin')
        db.add(parent)
        for kid in [tina,alan,erik]:
            db.add(PracticeRun(family_id=kid.family_id,learner_id=kid.id,content_id='keep',version=1,local_date=date(2026,10,21)))
            db.add(TopicProgress(family_id=kid.family_id,learner_id=kid.id,topic_id='keep',known=['known-card'],goals=['goal']))
        db.commit()
        before = {k.name:k.id for k in [alan,erik]}
        outcome = prepare(db,cfg)
        assert outcome['learners'] == before
        assert parent.family_id == real.id
        assert demo.status == 'suspended' and tina.archived
        assert alan.interests == 'music' and alan.tutor_daily_limit == 9 and erik.color == '#123456'
        assert len(list(db.scalars(select(PracticeRun)))) == 3
        assert all(p.known == ['known-card'] and p.goals == ['goal'] for p in db.scalars(select(TopicProgress)))
        with zipfile.ZipFile(outcome['backup']) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            assert 'ucilnica.db' in archive.namelist()
        assert manifest
        assert prepare(db,cfg)['changed'] is False
        assert len(list(db.scalars(select(Learner)))) == 3
    engine.dispose()


def test_local_setup_creates_only_requested_missing_profiles(tmp_path):
    cfg=Settings(data_dir=tmp_path,local_family='danijel'); cfg.ensure_dirs()
    engine=create_engine(f'sqlite:///{cfg.db_path.as_posix()}'); Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        result=prepare(db,cfg)
        assert set(result['learners']) == {'Alan','Erik'}
        assert list(db.scalars(select(User))) == []  # never invent credentials
        assert prepare(db,cfg)['changed'] is False
        with pytest.raises(ValueError,match='explicit local'):
            prepare(db,Settings(data_dir=tmp_path))
    engine.dispose()
