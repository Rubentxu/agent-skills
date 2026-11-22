import importlib.util
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from multi_agent_scheduler import schedule


def row(tid, deps=None, ready=True, priority='medium', **other):
    return {'id': tid, 'title': tid, 'archived': False, 'isReady': ready,
            'status': 'To Do', 'priority': priority, 'assignees': [],
            'dependencies': deps or [], **other}


def plan(tasks, resources, agents=None, details=None):
    return {'kind': 'multi-agent-plan-v1',
            'taskList': {'kind': 'task-list', 'schemaVersion': 1, 'tasks': tasks},
            'details': details or {t['id']: {**t, 'comments': []} for t in tasks},
            'resources': resources,
            'agents': agents if agents is not None else [
                {'id': 'worker-a', 'capacity': 1, 'skills': ['python']},
                {'id': 'worker-b', 'capacity': 1, 'skills': ['rust']}]
           }


class SchedulerTests(unittest.TestCase):
    def test_independent_work_allocated(self):
        a,b,c=row('A'),row('B'),row('C',['A','B'],ready=False)
        result=schedule(plan([a,b,c],{'A':['repo://project/a'],'B':['repo://project/b']}))
        self.assertEqual(result['status'],'PROPOSAL_ONLY')
        self.assertEqual({x['taskId'] for x in result['assignments']},{'A','B'})
        self.assertEqual({x['reason'] for x in result['skipped']},{'NOT_READY'})

    def test_conflicts_and_missing_scopes_fail_closed(self):
        items=[row('A'),row('B'),row('C')]
        result=schedule(plan(items,{'A':['repo://p/src'], 'B':['repo://p/src/b.py']}))
        self.assertEqual(len(result['assignments']),1)
        self.assertEqual({x['reason'] for x in result['skipped']},{'BATCH_CONFLICT','EFFECT_SCOPES_UNKNOWN'})

    def test_high_priority_and_skill_constraints(self):
        items=[row('A',priority='low',requiredSkills=['python']),
               row('B',priority='high',requiredSkills=['rust'])]
        result=schedule(plan(items,{'A':['repo://p/a'], 'B':['repo://p/b']}))
        self.assertEqual([(x['taskId'],x['agentId']) for x in result['assignments']],
                         [('B','worker-b'),('A','worker-a')])

    def test_dependency_cycle_detected(self):
        a,b=row('A',['B'],ready=False),row('B',['A'],ready=False)
        result=schedule(plan([a,b],{}))
        self.assertEqual(result['status'],'INVALID_DEPENDENCY_GRAPH')
        self.assertTrue(result['cycles'])

    def test_incomplete_view_rejected(self):
        with self.assertRaises(ValueError):
            schedule(plan([row('A')],{'A':['repo://p/a']},details={'B':{}}))


if __name__ == '__main__': unittest.main()
