"""Test-only server entry using the API's explicit clock dependency."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from server.tokenmeter_server.main import create_app

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fd',type=int,required=True);parser.add_argument('--database',required=True);parser.add_argument('--clock-file',type=Path,required=True)
    args=parser.parse_args()
    def clock():return int(args.clock_file.read_text().strip())
    uvicorn.run(create_app('sqlite:///'+args.database,clock=clock),fd=args.fd,proxy_headers=False)
