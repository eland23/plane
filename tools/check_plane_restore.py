#!/usr/bin/env python3
"""Run source contracts, demonstrate two bounded defects, restore and repeat."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parent
    helper='tools/plane_restore.py'
    sdk='docs/verification/HLB-434/native/asset_store_sdk.py'
    native='docs/verification/HLB-434/native/asset_store_rehearsal.py'
    cases=[('pass-known-state',helper,None,None,None,43,0),
           ('failure-asset-checksum',helper,"                    require(digest==row['sha256'], 'ASSET_HASH_MISMATCH')",None,'downloaded_asset',1,1),
           ('failure-record-preservation',helper,"            require(not (row_values(rows)-row_values(projected)), 'ORIGINAL_ROW_CHANGED')",None,'preservation_rejects',5,3),
           ('failure-sdk-endpoint',sdk,"and value['endpoint']==ENDPOINT and value['bucket']==BUCKET","and value['bucket']==BUCKET",'foreign_connection',6,2),
           ('failure-inspection-admission',native,"    require(listing.returncode==0,'INSPECTION_FAILED')","    if listing.returncode:return None",'indeterminate_docker_state',1,1),
           ('failure-receipt-cleanup',native,"            finally:cleanup()","            except OSError:raise\n            cleanup()",'receipt_failure_still',1,1),
           ('restore-and-repeat',helper,None,None,None,43,0)]
    receipts=[]
    for name,target,defect,replacement,selection,tests,failures in cases:
        with tempfile.TemporaryDirectory(prefix='plane-restore-contract-',dir='/var/tmp') as folder:
            clone=Path(folder)
            files=['tools/plane_restore.py','tools/tests/test_plane_restore.py','tools/tests/test_asset_store_guards.py']
            files+=['docs/verification/HLB-434/native/'+p.name for p in (source.parent/'docs/verification/HLB-434/native').glob('*.py')]
            for file in files:
                destination=clone/file;destination.parent.mkdir(parents=True,exist_ok=True)
                code=(source.parent/file).read_text()
                if defect and file==target:
                    if code.count(defect)!=1:raise RuntimeError('Defect boundary is not unique')
                    value=replacement if replacement is not None else defect[:len(defect)-len(defect.lstrip())]+'pass'
                    code=code.replace(defect,value)
                destination.write_text(code)
            command=[sys.executable,'-m','pytest','-q','tools/tests/test_plane_restore.py','tools/tests/test_asset_store_guards.py','-o','addopts=',
                     '--basetemp='+str(clone/'fixtures'),'--junitxml='+str(output/(name+'.xml'))]
            if selection:command+=['-k',selection]
            result=subprocess.run(command,cwd=clone,capture_output=True,text=True,timeout=120)
            (output/(name+'.log')).write_text(result.stdout+result.stderr)
            suites=list(ET.parse(output/(name+'.xml')).getroot().iter('testsuite'))
            counts={key:sum(int(s.get(key,'0')) for s in suites) for key in ['tests','failures','errors']}
            accepted=result.returncode==(1 if defect else 0) and counts=={'tests':tests,'failures':failures,'errors':0}
        receipts.append({'phase':name,'exit':result.returncode,'expected_failure':bool(defect),'counts':counts,
                         'accepted':accepted,'fixture_removed':not clone.exists()})
        if not accepted:break
    (output/'receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print(json.dumps(receipts))
    return 0 if len(receipts)==7 and all(r['accepted'] and r['fixture_removed'] for r in receipts) else 1


if __name__=='__main__':raise SystemExit(main())
