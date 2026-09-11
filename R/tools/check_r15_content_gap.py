"""Post-validation adversarial content-mutation audit; not part of frozen main family."""
from pathlib import Path
import sys,json
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from r12_r15.tests import trained
from r4_r7.monitor import feature_key
q,w=trained();trace={'repeats':1,'margin':.3};key=q.monitor_ref
before=q.current_reliability(trace);body=q.ledger.records[key].body;identity=id(q.monitor)
q.monitor.counts[feature_key(trace)]=[1,1]
after=q.current_reliability(trace)
result={'scope':'new audit injection after validation; main trials did not perform this mutation',
 'before':before,'after':after,'same_model_object':id(q.monitor)==identity,
 'historical_body_unchanged':q.ledger.records[key].body==body,
 'incorrectly_retained_current_status':after['status']=='supported' and after['probability']!=before['probability'],
 'finding':'Object binding and evidence validity do not authenticate mutable in-memory model contents.'}
if not result['incorrectly_retained_current_status']:raise AssertionError('counterexample not reproduced')
(ROOT/'results/r12_r15/CONTENT_MUTATION_COUNTEREXAMPLE.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
