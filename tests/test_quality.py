import json
import unittest
import test_autonomy
from emergence.autonomy import AutonomousDemo,run_mission
from emergence import quality
from emergence.db import LabError


class QualityTests(unittest.TestCase):
    setUp=test_autonomy.MissionTests.setUp
    create=test_autonomy.MissionTests.create
    def test_usefulness_rejection_stops_before_execution(self):
        class Reject(AutonomousDemo):
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs);v=json.loads(r.text)
                if json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])['stage']=='challenge':
                    v['verdict']='reject';v['checks'][0].update(passed=False,reason='No decision changes: this setup simply encodes its answer.')
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(call_limit=12,cycle_limit=1),Reject())
        self.assertEqual(len(state['turns']),4)
        self.execute.assert_not_called()
        self.assertEqual(state['reports'],[])
        self.assertIn('usefulness gate',state['missions'][0]['stop_reason'])

    def test_one_revision_and_fresh_review_of_changed_edition(self):
        class Revise(AutonomousDemo):
            reads=0
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs);v=json.loads(r.text)
                context=json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])
                if context['stage']=='read':
                    self.reads+=1
                    assert context['dialogue']==[]
                    if self.reads==1:
                        v['verdict']='revise';v['checks'][2].update(passed=False,reason='Takeaway must say this is a workflow demonstration.')
                if context['stage']=='write' and context['state']['editorial_revision']:
                    v['report']['takeaway']='This workflow demonstration shows how to document one regression test for withdrawn memory entries.'
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(call_limit=12,cycle_limit=1),Revise())
        self.assertEqual(len(state['turns']),10)
        self.assertEqual(state['reports'][0]['status'],'ready')
        self.assertEqual(len(state['report_versions']),2)
        first,second=state['report_versions']
        self.assertNotEqual(first['content_sha256'],second['content_sha256'])
        self.assertEqual([r['version_id'] for r in state['report_reviews']],[first['id'],second['id']])

    def test_unchanged_rewrite_cannot_be_approved(self):
        class Unchanged(AutonomousDemo):
            reads=0
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs);v=json.loads(r.text)
                if json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])['stage']=='read':
                    self.reads+=1
                    if self.reads==1:
                        v['verdict']='revise';v['checks'][2].update(passed=False,reason='The takeaway needs a concrete change.')
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(call_limit=12,cycle_limit=1),Unchanged())
        self.assertEqual(state['reports'][0]['status'],'withheld')
        self.assertIn('unchanged',state['reports'][0]['reason'])

    def test_allowance_exhaustion_cannot_make_report_ready(self):
        class NeedsWork(AutonomousDemo):
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs);v=json.loads(r.text)
                if json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])['stage']=='read':
                    v['verdict']='revise';v['checks'][3].update(passed=False,reason='what_to_do does not identify a useful decision.')
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(call_limit=8,cycle_limit=1),NeedsWork())
        self.assertEqual(state['reports'][0]['status'],'withheld')
        self.assertEqual(state['claims'][0]['status'],'peer_checked')
        with self.lab.tx() as db:
            with self.assertRaises(LabError):quality.download(db,state['reports'][0]['id'])

    def test_wrong_evidence_reference_blocks_even_positive_reviews(self):
        class WrongReference(AutonomousDemo):
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs);v=json.loads(r.text)
                if json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])['stage']=='write':
                    v['report']['evidence_ids']=['run_invented']
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(call_limit=8,cycle_limit=1),WrongReference())
        self.assertEqual(state['reports'][0]['status'],'withheld')

    def test_escaped_standalone_note_and_withdrawal_check(self):
        class Markup(AutonomousDemo):
            def generate(self,*args,**kwargs):
                r=super().generate(*args,**kwargs);v=json.loads(r.text)
                if v['report']['title']:v['report']['title']='<script>alert(1)</script>'
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(cycle_limit=1),Markup())
        report=state['reports'][0]
        with self.lab.tx() as db:
            page=quality.download(db,report['id']).decode()
            self.assertNotIn('<script>',page)
            self.assertIn('&lt;script&gt;',page)
            self.assertIn('SYNTHETIC REHEARSAL',page)
            db.execute("UPDATE mission_claims SET status='retracted' WHERE id=?",(report['claim_id'],))
            with self.assertRaises(LabError):quality.download(db,report['id'])

    def test_refine_existing_finding_uses_no_new_experiment(self):
        source=self.create(cycle_limit=1)
        run_mission(self.lab,source)
        calls=self.execute.call_count
        mid=self.missions.refine(source)['id']
        self.missions.control(mid,'start')
        state=run_mission(self.lab,mid)
        self.assertEqual([t['stage'] for t in state['turns']],['write','read'])
        self.assertEqual(self.execute.call_count,calls)
        self.assertEqual(state['reports'][0]['status'],'ready')
        self.assertEqual(len(state['experiments']),2)

    def test_old_mission_keeps_six_stage_protocol(self):
        mid=self.create(cycle_limit=1)
        with self.lab.tx() as db:
            ctx=json.loads(self.missions.get(db,mid)['context_json']);ctx.pop('quality_version')
            db.execute('UPDATE missions SET context_json=? WHERE id=?',(json.dumps(ctx),mid))
        state=run_mission(self.lab,mid)
        self.assertEqual(len(state['turns']),6)
        self.assertEqual(state['reports'],[])

    def test_refine_uses_the_selected_findings_context(self):
        source=self.create(cycle_limit=1)
        state=run_mission(self.lab,source)
        original=state['missions'][0]['context']['candidate']
        with self.lab.tx() as db:
            ctx=json.loads(self.missions.get(db,source)['context_json'])
            ctx['candidate']={'question':'A later, unrelated investigation'}
            ctx['brief']={k:'Unrelated context' for k in quality.BRIEF_FIELDS}
            db.execute('UPDATE missions SET context_json=? WHERE id=?',(json.dumps(ctx),source))
        mid=self.missions.refine(source)['id']
        self.missions.control(mid,'start')
        turn=self.missions.reserve(mid)
        self.assertEqual(turn['payload']['state']['candidate'],original)
        self.assertNotEqual(turn['payload']['state']['brief']['decision'],'Unrelated context')
        self.assertEqual(turn['payload']['finding']['id'],state['claims'][0]['id'])

    def test_generic_praise_cannot_approve_a_report(self):
        class RubberStamp(AutonomousDemo):
            def generate(self,*args,**kwargs):
                r=super().generate(*args,**kwargs);v=json.loads(r.text)
                if len(v['checks'])==5:
                    for c in v['checks']:c.update(reason='Looks good',quote='made up passage',evidence_id='invented')
                r.text=json.dumps(v);return r
        state=run_mission(self.lab,self.create(call_limit=8,cycle_limit=1),RubberStamp())
        self.assertEqual(state['reports'][0]['status'],'withheld')

    def test_reader_feedback_guides_future_missions_without_blocking(self):
        state=run_mission(self.lab,self.create(cycle_limit=1))
        report=state['reports'][0]
        with self.lab.tx() as db:
            quality.feedback(db,report['id'],'not_useful','Too obvious; test an actual cached retrieval implementation next.')
        mid=self.create()
        turn=self.missions.reserve(mid)
        self.assertEqual(turn['payload']['human_feedback'][0]['value'],'not_useful')
        self.assertIn('cached retrieval',turn['payload']['human_feedback'][0]['reason'])

    def test_withdrawn_findings_cannot_reenter_through_feedback(self):
        state=run_mission(self.lab,self.create(cycle_limit=1))
        report=state['reports'][0]
        with self.lab.tx() as db:
            quality.feedback(db,report['id'],'useful','This gave me a concrete implementation decision.')
            db.execute("UPDATE mission_claims SET status='retracted' WHERE id=?",(report['claim_id'],))
        mid=self.create()
        turn=self.missions.reserve(mid)
        self.assertEqual(turn['payload']['human_feedback'],[])
        self.assertNotIn(report['claim_id'],[c['id'] for c in turn['payload']['knowledge']])
