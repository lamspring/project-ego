"""Start, poll, read, or stop a persistent background command."""
import argparse, json, sys
from ego_core import Ego, EgoError, dumps
from ego_async import AsyncJobs


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    p.add_argument('command',choices=['start','poll','output','stop']);p.add_argument('args',nargs='*')
    p.add_argument('--work-id');p.add_argument('--cwd');p.add_argument('--reason',default='Worker requested stop')
    a=p.parse_args()
    with Ego(a.root) as core:
        jobs=AsyncJobs(core)
        if a.command=='start':
            spec=json.load(open(a.args[0],encoding='utf-8'))
            out=jobs.start(spec['command'],a.work_id or spec.get('work_id'),a.cwd or spec.get('cwd'))
        elif a.command=='poll':out=jobs.poll(a.args[0])
        elif a.command=='output':out=jobs.output(a.args[0])
        else:out=jobs.stop(a.args[0],a.reason)
        print(dumps(out))


if __name__=='__main__':
    try:main()
    except EgoError as e:print(json.dumps({'error':str(e)},ensure_ascii=False));sys.exit(2)
