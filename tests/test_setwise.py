import tempfile
import unittest
from pathlib import Path
from app import create_app
from app.database.repository import get_state
from app.services.planning_service import generate_plan
from app.services.agent_tools import classify_terrain


class TerrainClassificationTests(unittest.TestCase):

    def test_terrain_classification(self):
        self.assertEqual(classify_terrain(-10), "Slab")
        self.assertEqual(classify_terrain(0), "Vertical")
        self.assertEqual(classify_terrain(20), "Overhang")
        self.assertEqual(
            classify_terrain(45),
            "Steep overhang",
        )

class SetWiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.tmp.name) / 'test.db')})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        with self.app.app_context():
            return get_state()
        
    def post(self, action, **data):
        return self.client.post('/action', data={'action': action, 'page':'walls', **data}, follow_redirects=True)
    
    def test_pages(self):
        for page in ['overview','walls','targets','planner']:
            self.assertEqual(self.client.get('/?page='+page).status_code, 200)
        self.assertEqual(self.client.get('/?page=nope').status_code, 404)

    def test_add_wall_and_climb(self):
        self.post('add_wall', name='Training Wall', angle='35')
        state = self.state()
        wall = next(w for w in state['walls'] if w['name']=='Training Wall')
        self.post('add_climb', wall_id=wall['id'], grade='V4', sub='Middle', style='Compression')
        self.assertTrue(any(c['wallId']==wall['id'] and c['grade']=='V4' for c in self.state()['climbs']))

    def test_invalid_input_does_not_save(self):
        before = len(self.state()['walls'])
        self.post('add_wall', name='Invalid', angle='200')
        self.assertEqual(len(self.state()['walls']), before)

    def test_plan_and_reset(self):
        state = self.state()
        self.assertEqual(len(generate_plan(state)), 10)
        self.post('generate_plan')
        self.assertEqual(len(self.state()['plan']), 10)
        self.post('save_plan')
        self.assertEqual(len([c for c in self.state()['climbs'] if c['status']=='Planned']), 10)
        self.post('confirm_reset', confirm='yes')
        self.assertFalse(any(c['status']=='Active' and c['wallId'] in {'w1','w3'} for c in self.state()['climbs']))
        self.post('activate_planned')
        self.assertEqual(len([c for c in self.state()['climbs'] if c['status']=='Planned']), 0)

    def test_target_save(self):
        data = {'action':'save_targets', 'page':'targets'}
        state = self.state()
        for g in state['gradeTargets']:
            for sub in ['Easy','Middle','Hard']:
                data[f'grade_{g}_{sub}'] = '2'
        for style in state['styleTargets']:
            data[f'style_{style}'] = '9'
        self.client.post('/action', data=data)
        self.assertEqual(self.state()['gradeTargets']['V3'], [2,2,2])

    def test_gyms_have_separate_inventory(self):
        # Add a wall to Gym A.
        response = self.client.post(
            "/action",
            data={
                "gym_id": "gym-a",
                "page": "walls",
                "action": "add_wall",
                "name": "Test Overhang",
                "angle": "30"
            }
        )
        self.assertEqual(response.status_code, 302)
        # Check that Gym A contains the new wall.
        response_a = self.client.get("/?gym_id=gym-a")
        self.assertIn(b"Test Overhang", response_a.data)
        # Check that Gym B doesn't contain Gym A's wall.
        response_b = self.client.get("/?gym_id=gym-b")
        self.assertNotIn(b"Test Overhang", response_b.data)

    def test_invalid_gym_id(self):
        response = self.client.get("/?gym_id=unknown-gym")
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
