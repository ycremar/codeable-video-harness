import argparse
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ms=importlib.util.spec_from_file_location('model_api',Path(__file__).resolve().parents[1]/'adapters/model_api.py')
a=importlib.util.module_from_spec(ms);ms.loader.exec_module(a)

class APIAdapterTests(unittest.TestCase):
    def test_no_spend_without_explicit_optin(self):
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(PermissionError):a.run(argparse.Namespace(allow_paid_api=False),{})
            request.assert_not_called()
    def test_missing_key_no_network(self):
        args=argparse.Namespace(allow_paid_api=True,provider='openai')
        with patch.dict('os.environ',{},clear=True),patch('urllib.request.urlopen') as request:
            with self.assertRaises(ValueError):a.run(args,{})
            request.assert_not_called()
    def test_openai_image_and_json_request_shape(self):
        p=a.payload('openai','explicit-model',{},['abc'],1234)
        self.assertFalse(p['store']);self.assertEqual(p['input'][0]['content'][1]['type'],'input_image')
        self.assertEqual(p['text']['format']['type'],'json_object')
    def test_anthropic_image_request_shape(self):
        p=a.payload('anthropic','explicit-model',{},['abc'],1234)
        self.assertEqual(p['messages'][0]['content'][1]['source']['media_type'],'image/jpeg')
    def test_incomplete_generation_rejected(self):
        with self.assertRaises(ValueError):a.extract('openai',{'status':'incomplete'})
        with self.assertRaises(ValueError):a.extract('anthropic',{'stop_reason':'max_tokens'})
    def test_provider_provenance_does_not_trust_generated_claim(self):
        raw={'status':'completed','model':'observed-model','id':'fixture','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'author':{'model':'invented'}})}]}]}
        r=a.extract('openai',raw);self.assertEqual(r['author']['returned_model'],'observed-model')
    def test_inspection_preserves_limits(self):
        raw={'stop_reason':'end_turn','content':[{'type':'text','text':'{"inspection":{"limitations":[]}}'}]}
        self.assertIn('no full-motion or audio',a.extract('anthropic',raw)['inspection']['limitations'][0])
