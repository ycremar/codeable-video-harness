#!/usr/bin/env python3
"""Concrete optional OpenAI/Anthropic author adapter. No API calls without opt-in.

Reads a vch-author-v1 request from stdin, returns response JSON on stdout.
The inspection request includes actual decoded contact-sheet pixels. It cannot
watch motion or listen to audio and must preserve those review limitations.
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SYSTEM='You are a video coding agent. Follow the supplied frozen contract and author protocol. Return a single valid JSON object with no markdown. Do not change requirement IDs or thresholds. Do not invent human approval, model provenance, or evidence.'


def prepare_packet(packet):
    packet=json.loads(json.dumps(packet));images=[]
    if packet.get('phase')=='inspect':
        feedback=packet.get('feedback',{});paths=feedback.get('rendered_frames',[])
        if len(paths)!=2:raise ValueError('Inspection needs contact sheet and MP4 paths')
        sheet,video=map(Path,paths)
        if sheet.name!='contact-sheet.jpg' or video.name!='video.mp4' or sheet.parent.resolve()!=video.parent.resolve():
            raise ValueError('Unexpected inspection artifact paths')
        if sheet.stat().st_size>10*1024*1024:raise ValueError('Contact sheet exceeds adapter image budget')
        digest=hashlib.sha256(video.read_bytes()).hexdigest()
        images.append(base64.b64encode(sheet.read_bytes()).decode())
        packet['inspection_capability']={'video_sha256':digest,'images':['decoded MP4 contact sheet'],
            'limitations':['No full-motion playback or audio listening by this adapter.','No human approval.'],
            'instruction':'Inspect the supplied image pixels. Copy video_sha256 into your inspection. Cite visible frames/timestamps. Keep audio, motion and subjective human requirements pending.'}
    elif packet.get('feedback',{}):
        previous=packet['feedback'].get('previous_response')
        artifacts=packet['feedback'].get('rendered_frames',[])
        if not previous and len(artifacts)==2:
            video=Path(artifacts[1])
            if video.name=='video.mp4' and len(video.parents)>3:
                previous=str(video.parents[3]/'author-response.json')
        if previous:
            p=Path(previous)
            if p.name!='author-response.json' or p.stat().st_size>2*1024*1024:raise ValueError('Invalid previous response artifact')
            packet['previous_candidate']=json.loads(p.read_text())
    return packet,images


def payload(provider,model,packet,images,max_tokens):
    text=json.dumps(packet,ensure_ascii=False)
    if provider=='openai':
        content=[{'type':'input_text','text':text}]+[{'type':'input_image','image_url':'data:image/jpeg;base64,'+x,'detail':'high'} for x in images]
        return {'model':model,'instructions':SYSTEM,'input':[{'role':'user','content':content}],
                'max_output_tokens':max_tokens,'text':{'format':{'type':'json_object'}},'store':False}
    content=[{'type':'text','text':text}]+[{'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':x}} for x in images]
    return {'model':model,'system':SYSTEM,'max_tokens':max_tokens,'messages':[{'role':'user','content':content}]}


def extract(provider,raw):
    if provider=='openai':
        if raw.get('status')!='completed':raise ValueError('OpenAI response not completed; no partial candidate accepted')
        parts=[c['text'] for o in raw.get('output',[]) if o.get('type')=='message' for c in o.get('content',[]) if c.get('type')=='output_text']
    else:
        if raw.get('stop_reason')!='end_turn':raise ValueError('Anthropic response did not finish normally')
        parts=[c['text'] for c in raw.get('content',[]) if c.get('type')=='text']
    response=json.loads(''.join(parts))
    if not isinstance(response,dict):raise ValueError('Author response must be a JSON object')
    response['author']={'provider':provider,'returned_model':raw.get('model'),'response_id':raw.get('id'),'usage':raw.get('usage'),
                        'provenance':'reported by provider API response; not inferred from generated text'}
    if response.get('inspection'):
        response['inspection'].setdefault('limitations',[]).append('API adapter inspected static decoded frames only; no full-motion or audio review.')
    return response


def run(args,packet):
    if not args.allow_paid_api:raise PermissionError('No request sent. Enable --allow-paid-api only with an authorized API budget.')
    key_name='OPENAI_API_KEY' if args.provider=='openai' else 'ANTHROPIC_API_KEY'
    key=os.environ.get(key_name)
    if not key:raise ValueError(f'Missing {key_name}; no request sent')
    prepared,images=prepare_packet(packet)
    data=payload(args.provider,args.model,prepared,images,args.max_output_tokens)
    url='https://api.openai.com/v1/responses' if args.provider=='openai' else 'https://api.anthropic.com/v1/messages'
    headers={'Content-Type':'application/json'}
    if args.provider=='openai':headers['Authorization']='Bearer '+key
    else:headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    req=urllib.request.Request(url,data=json.dumps(data).encode(),headers=headers,method='POST')
    # Exactly one request. No hidden retry on a possibly billed timeout.
    try:
        with urllib.request.urlopen(req,timeout=args.timeout) as r:raw=json.load(r)
    except urllib.error.HTTPError as exc:raise RuntimeError(f'{args.provider} HTTP {exc.code}; response body withheld from logs') from None
    return extract(args.provider,raw)


def main():
    p=argparse.ArgumentParser();p.add_argument('--provider',required=True,choices=['openai','anthropic']);p.add_argument('--model',required=True)
    p.add_argument('--allow-paid-api',action='store_true');p.add_argument('--max-output-tokens',type=int,default=12000);p.add_argument('--timeout',type=int,default=240)
    args=p.parse_args()
    if not 100<=args.max_output_tokens<=32000:p.error('max-output-tokens must be 100..32000')
    try:result=run(args,json.load(sys.stdin));print(json.dumps(result,ensure_ascii=False))
    except (ValueError,PermissionError,RuntimeError,OSError) as exc:print(str(exc),file=sys.stderr);raise SystemExit(2)
if __name__=='__main__':main()
