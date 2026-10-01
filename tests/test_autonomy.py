import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from emergence.autonomy import AutonomousDemo, Missions, MissionManager, run_mission
from emergence.db import Lab, LabError, now, uid
from emergence.providers import InferenceError


def execution(directory,code,**kwargs):
    return {"status":"passed","data":{"verified":True},"stdout":"{\"verified\":true}","stderr":"","code_sha256":"fixture"}


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab=Lab(self.temp.name)
        self.missions=Missions(self.lab)
        self.addCleanup(patch.stopall)
        self.execute=patch('emergence.autonomy.run_python',side_effect=execution).start()
        patch('emergence.autonomy.capability',return_value={"available":True}).start()

    def create(self,**kwargs):
        identifier=self.missions.create({"provider":"demo","call_limit":18,"cycle_limit":2,**kwargs})['id']
        self.missions.control(identifier,'start')
        return identifier

    def test_two_cycles_without_owner_intervention(self):
        mid=self.create()
        state=run_mission(self.lab,mid)
        self.assertEqual(state['missions'][0]['status'],'completed')
        self.assertEqual(state['missions'][0]['calls_used'],16)
        self.assertEqual(len(state['claims']),2)
        self.assertEqual(self.execute.call_count,4)
        self.assertTrue(all(c['status']=='peer_checked' for c in state['claims']))
        exported=self.missions.export()
        second=json.loads(exported['mission_turns'][8]['prompt_json'])
        self.assertTrue(second['state']['next_question'])
        self.assertTrue(second['knowledge'])
        self.assertIn('mission_claim_events',exported)
        assessment=json.loads(exported['mission_turns'][4]['prompt_json'])
        self.assertEqual(assessment['stage'],'assess')
        self.assertTrue(all(e.get('code') for e in assessment['experiments']))

    def test_consultation_is_addressed_and_caller_resumes(self):
        class Consultation(AutonomousDemo):
            asked=False
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs)
                p=json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])
                if p['stage']=='explore' and not self.asked:
                    value=json.loads(r.text)
                    value.update(ask_agent='critic',question_for_agent='Which confound matters most?')
                    r.text=json.dumps(value);self.asked=True
                return r
        mid=self.create(call_limit=10,cycle_limit=1)
        state=run_mission(self.lab,mid,Consultation())
        self.assertEqual([t['stage'] for t in state['turns']],['explore','consult','explore','challenge','experiment','verify','assess','conclude','write','read'])
        self.assertEqual(state['turns'][1]['agent'],'critic')
        self.assertEqual(len(state['claims']),1)

    def test_call_limit_applies_to_invalid_outputs(self):
        class Invalid(AutonomousDemo):
            def generate(self,*args,**kwargs):
                r=super().generate(*args,**kwargs);r.text='invalid response';return r
        mid=self.create(call_limit=8)
        state=run_mission(self.lab,mid,Invalid())
        self.assertEqual(len(state['turns']),2)
        self.assertEqual(state['missions'][0]['status'],'failed')
        self.assertEqual(state['turns'][0]['response_json'],'invalid response')
        self.execute.assert_not_called()

    def test_uncertain_provider_request_is_not_repeated(self):
        class Timeout:
            calls=0
            def generate(self,*args,**kwargs):
                self.calls+=1
                raise InferenceError('timeout',0,{'usage_unknown':True})
        engine=Timeout();mid=self.create()
        state=run_mission(self.lab,mid,engine)
        self.assertEqual(engine.calls,1)
        self.assertEqual(state['missions'][0]['status'],'paused')
        self.assertTrue(json.loads(state['turns'][0]['usage_json'])['usage_unknown'])

    def test_stop_while_inference_pending_retains_receipt_without_execution(self):
        owner=self
        class Stop(AutonomousDemo):
            def generate(self,prompt,*args,**kwargs):
                result=super().generate(prompt,*args,**kwargs)
                if json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])['stage']=='experiment':
                    owner.missions.control(mid,'stop')
                return result
        mid=self.create()
        state=run_mission(self.lab,mid,Stop())
        self.execute.assert_not_called()
        self.assertEqual(state['turns'][-1]['status'],'interrupted')
        self.assertIsNotNone(state['turns'][-1]['usage_json'])
        self.assertEqual(state['missions'][0]['stop_reason'],'Owner stop requested.')
        with self.assertRaises(LabError):self.missions.control(mid,'pause')
        with self.assertRaises(LabError):self.missions.control(mid,'start')

    def test_concurrent_reservations_have_one_winner(self):
        mid=self.create()
        def reserve(_):
            try:return self.missions.reserve(mid)
            except LabError:return None
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            results=list(pool.map(reserve,range(4)))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_restart_does_not_replay_inflight_request(self):
        mid=self.create();self.missions.reserve(mid)
        manager=MissionManager(self.lab)
        state=manager.missions.state(mid)
        self.assertEqual(state['turns'][0]['status'],'interrupted')
        self.assertEqual(state['missions'][0]['status'],'paused')
        self.assertEqual(state['missions'][0]['calls_used'],1)

    def test_demo_knowledge_excluded_from_live_context(self):
        run_mission(self.lab,self.create())
        mid=self.create(provider='codex')
        turn=self.missions.reserve(mid)
        self.assertEqual(turn['payload']['knowledge'],[])

    def test_failed_verification_cannot_be_peer_checked(self):
        self.execute.side_effect=lambda *a,**k:{**execution(*a,**k),'data':{'verified':False}}
        state=run_mission(self.lab,self.create(cycle_limit=1))
        self.assertEqual(state['claims'][0]['status'],'provisional')

    def test_unavailable_executor_cannot_be_peer_checked(self):
        self.execute.side_effect=lambda *a,**k:{'status':'unavailable','data':None}
        state=run_mission(self.lab,self.create(cycle_limit=1))
        self.assertEqual(state['claims'][0]['status'],'provisional')

    def test_consultation_limit_cannot_skip_required_execution(self):
        class Chatty(AutonomousDemo):
            def generate(self,prompt,*args,**kwargs):
                r=super().generate(prompt,*args,**kwargs)
                stage=json.loads(prompt.split('\nMISSION_CONTEXT\n')[1])['stage']
                value=json.loads(r.text)
                if stage!='consult':value.update(ask_agent='coordinator',question_for_agent='Advice?')
                r.text=json.dumps(value);return r
        state=run_mission(self.lab,self.create(call_limit=12,cycle_limit=1),Chatty())
        self.assertEqual(sum(t['stage']=='consult' for t in state['turns']),2)
        self.assertEqual(self.execute.call_count,2)
        self.assertEqual(state['missions'][0]['status'],'completed')

    def test_unsupported_retraction_is_dispute_only(self):
        first=run_mission(self.lab,self.create(cycle_limit=1))['claims'][0]['id']
        class Retract(AutonomousDemo):
            def generate(self,*args,**kwargs):
                r=super().generate(*args,**kwargs);v=json.loads(r.text)
                v['claim_changes']=[{'claim_id':first,'action':'retract','reason':'Unverified objection'}]
                r.text=json.dumps(v);return r
        self.execute.side_effect=lambda *a,**k:{'status':'failed','data':None}
        run_mission(self.lab,self.create(cycle_limit=1),Retract())
        snapshot=self.missions.export()
        self.assertEqual(next(c for c in snapshot['mission_claims'] if c['id']==first)['status'],'peer_checked')
        self.assertIn('disputed',[e['action'] for e in snapshot['mission_claim_events']])

    def test_finite_allowance_stops_before_incomplete_second_cycle(self):
        state=run_mission(self.lab,self.create(call_limit=9))
        self.assertEqual(state['missions'][0]['status'],'exhausted')
        self.assertEqual(len(state['turns']),8)


class OverviewTests(unittest.TestCase):
    setUp=MissionTests.setUp

    def mission(self,provider='codex',status='completed'):
        mid=self.missions.create({'provider':provider})['id']
        with self.lab.tx() as db:
            db.execute('UPDATE missions SET status=? WHERE id=?',(status,mid))
        return mid

    def claim(self,mid,status='peer_checked'):
        cid=uid('claim')
        with self.lab.tx() as db:
            db.execute('INSERT INTO mission_claims VALUES(?,?,?,?,?,?,?,?,?)',
                       (cid,mid,1,'Fixture finding',status,'[]','Fixture limits',now(),now()))
        return cid

    def report(self,mid,cid,status='ready',timestamp=None,title='Fixture report'):
        rid,vid=uid('report'),uid('edition')
        timestamp=timestamp or now()
        content={'title':title,'takeaway':'Current-edition takeaway','next_step':'Try a further test.'}
        with self.lab.tx() as db:
            db.execute('INSERT INTO mission_reports VALUES(?,?,?,?,?,?,?,?)',
                       (rid,mid,cid,status,vid,'Fixture reason',timestamp,timestamp))
            db.execute('INSERT INTO mission_report_versions VALUES(?,?,?,?,?,?)',
                       (vid,rid,'fixture-turn',json.dumps(content),'fixture-hash',timestamp))
        return rid

    def test_empty_overview_has_zero_counts_and_no_reports(self):
        state=self.missions.state()
        self.assertIsNone(state['selected'])
        self.assertEqual(state['overview']['recent_reports'],[])
        self.assertEqual(state['overview']['demo_reports'],[])
        self.assertTrue(all(value==0 for group in state['overview']['counts'].values() for value in group.values()))

    def test_global_counts_separate_demo_results_and_do_not_count_completion_as_success(self):
        source=self.mission()
        refinement=self.mission(status='paused')
        empty=self.mission()
        demo=self.mission(provider='demo',status='running')
        self.mission(provider='demo',status='ready')
        checked=self.claim(source)
        self.claim(source,status='provisional')
        self.report(source,checked)
        refined=self.report(refinement,checked)
        self.report(demo,self.claim(demo))
        with self.lab.tx() as db:
            for ordinal,usage in enumerate(({'tokens':{'input_tokens':10,'output_tokens':4}},None),1):
                db.execute('''INSERT INTO mission_turns
                    (id,mission_id,ordinal,agent,stage,cycle,status,prompt_json,usage_json,started_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (uid('turn'),source,ordinal,'scout','explore',1,'failed','{}',json.dumps(usage) if usage else None,now()))
        state=self.missions.state(refinement)
        counts=state['overview']['counts']
        self.assertEqual(counts['live'],{'total':3,'running':0,'paused':1,'ready':0,'completed':2,
                                       'exhausted':0,'failed':0,'checked_findings':1,'ready_reports':2})
        self.assertEqual(counts['demo'],{'total':2,'running':1,'paused':0,'ready':1,'completed':0,
                                       'exhausted':0,'failed':0,'checked_findings':1,'ready_reports':1})
        self.assertEqual(counts['all']['total'],5)
        self.assertEqual(counts['all']['checked_findings'],2)
        self.assertEqual(counts['all']['ready_reports'],3)
        missions={m['id']:m for m in state['missions']}
        self.assertEqual((missions[source]['calls_used'],missions[source]['input_tokens'],missions[source]['output_tokens']),(2,10,4))
        self.assertEqual(missions[refinement]['checked_findings_count'],0)
        self.assertEqual(missions[refinement]['ready_reports_count'],1)
        self.assertEqual(missions[empty]['ready_reports_count'],0)
        # Detail selection and the refinement's original supporting claim remain available.
        self.assertEqual(state['selected'],refinement)
        self.assertEqual([r['id'] for r in state['reports']],[refined])
        self.assertEqual([c['id'] for c in state['claims']],[checked])
        self.execute.assert_not_called()

    def test_ready_reports_disappear_when_supporting_claim_is_no_longer_checked(self):
        mid=self.mission()
        cid=self.claim(mid)
        self.report(mid,cid)
        self.assertEqual(self.missions.state(mid)['overview']['counts']['live']['ready_reports'],1)
        for status in ('retracted','superseded','provisional'):
            with self.subTest(claim_status=status):
                # Even a stale ready report row cannot promote a withdrawn claim.
                with self.lab.tx() as db:
                    db.execute('UPDATE mission_claims SET status=? WHERE id=?',(status,cid))
                state=self.missions.state(mid)
                self.assertEqual(state['overview']['recent_reports'],[])
                self.assertEqual(state['overview']['counts']['live']['ready_reports'],0)
                self.assertEqual(state['overview']['counts']['live']['checked_findings'],0)
                self.assertEqual(state['missions'][0]['ready_reports_count'],0)

    def test_unready_or_missing_current_editions_are_not_presented_as_ready(self):
        mid=self.mission()
        cid=self.claim(mid)
        for status in ('draft','withheld','changes_requested','withdrawn'):
            self.report(mid,cid,status=status)
        invalid=self.report(mid,cid)
        with self.lab.tx() as db:
            db.execute('UPDATE mission_reports SET current_version=NULL WHERE id=?',(invalid,))
        overview=self.missions.state(mid)['overview']
        self.assertEqual(overview['counts']['live']['checked_findings'],1)
        self.assertEqual(overview['counts']['live']['ready_reports'],0)
        self.assertEqual(overview['recent_reports'],[])

    def test_recent_reports_use_current_edition_with_separate_live_and_demo_limits(self):
        live=self.mission()
        live_claim=self.claim(live)
        live_ids=[self.report(live,live_claim,timestamp=f'2026-01-0{i}T00:00:00+00:00',title=f'Live {i}') for i in range(1,7)]
        demo=self.mission(provider='demo')
        demo_claim=self.claim(demo)
        demo_ids=[self.report(demo,demo_claim,timestamp=f'2026-02-0{i}T00:00:00+00:00') for i in range(1,8)]
        # Old edition content must not become the preview merely because it exists.
        with self.lab.tx() as db:
            db.execute('INSERT INTO mission_report_versions VALUES(?,?,?,?,?,?)',
                       (uid('edition'),live_ids[-1],'older-turn',json.dumps({'title':'Obsolete title'}),'old-hash',now()))
        overview=self.missions.state(demo)['overview']
        self.assertEqual([r['id'] for r in overview['recent_reports']],list(reversed(live_ids[-5:])))
        self.assertEqual([r['id'] for r in overview['demo_reports']],list(reversed(demo_ids[-3:])))
        self.assertEqual(overview['recent_reports'][0]['title'],'Live 6')
        self.assertEqual(overview['recent_reports'][0]['takeaway'],'Current-edition takeaway')
        self.assertEqual(overview['recent_reports'][0]['claim_status'],'peer_checked')
        self.assertTrue(all(r['provider']=='codex' for r in overview['recent_reports']))
        self.assertTrue(all(r['provider']=='demo' for r in overview['demo_reports']))
        self.assertEqual(overview['counts']['live']['ready_reports'],6)
        self.assertEqual(overview['counts']['demo']['ready_reports'],7)


if __name__=='__main__':unittest.main()
