#!/usr/bin/env python3
"""Fail-closed offline T080 provenance/semantic audit."""
import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

CHECKPOINT_SHA="a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
REPORT_SCHEMA="t080-value-target-semantics-audit-v1"; MANIFEST_SCHEMA="t080-retention-manifest-v1"
ROOT=Path(__file__).resolve().parents[1]

def digest(p):
 h=hashlib.sha256(); n=0
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): h.update(b); n+=len(b)
 return h.hexdigest(),n

def _find(x,key):
 if isinstance(x,dict):
  if key in x:return x[key]
  for v in x.values():
   z=_find(v,key)
   if z is not None:return z
 if isinstance(x,(list,tuple)):
  for v in x:
   z=_find(v,key)
   if z is not None:return z
 return None

def load_checkpoint_provenance(path):
 try: import torch
 except ImportError as e: raise RuntimeError("T080 fail closed: torch is required to load checkpoint provenance") from e
 obj=torch.load(path,map_location="cpu",weights_only=False)
 p=_find(obj,"training_data_provenance")
 if not isinstance(p,dict):raise RuntimeError("T080 fail closed: checkpoint training_data_provenance missing")
 return p,_find(obj,"checkpoint_metadata") or {}

def _stable(v,where):
 if not isinstance(v,dict):return {"status":"missing","identity":None}
 keys=("stable_id","action_id","kind","label","occurrence")
 if any(v.get(k) is None for k in keys):raise RuntimeError(f"T080 fail closed: incomplete {where} identity")
 return {"status":"available","identity":{k:v[k] for k in keys}}

def audit(checkpoint,trainer,checkpoint_loader=load_checkpoint_provenance):
 checkpoint=Path(checkpoint).resolve(); trainer=Path(trainer).resolve(); cs,cb=digest(checkpoint)
 if cs!=CHECKPOINT_SHA:raise RuntimeError("T080 fail closed: checkpoint SHA-256 mismatch")
 cp,cpmeta=checkpoint_loader(checkpoint); ts,tb=digest(trainer)
 if cp.get("trainer_input_sha256")!=ts or cp.get("trainer_input_path")!=str(trainer):raise RuntimeError("T080 fail closed: checkpoint trainer identity mismatch")
 if cp.get("byte_count",cp.get("trainer_input_bytes"))!=tb:raise RuntimeError("T080 fail closed: checkpoint trainer byte_count mismatch")
 if cp.get("trainer_record_count",cp.get("record_count"))!=4:raise RuntimeError("T080 fail closed: checkpoint trainer record count mismatch")
 if not cp.get("trainer_input_artifact_id","").endswith(ts):raise RuntimeError("T080 fail closed: checkpoint trainer artifact_id mismatch")
 rows=[]; meta=None; wrappers=0
 for no,line in enumerate(trainer.open(encoding="utf-8"),1):
  x=json.loads(line)
  if x.get("type")=="metadata":wrappers+=1;meta=x.get("metadata")
  elif x.get("type")=="record" and isinstance(x.get("record"),dict):rows.append(x["record"])
  else:raise RuntimeError(f"T080 fail closed: invalid trainer line {no}")
 if wrappers!=1 or len(rows)!=4 or not isinstance(meta,dict):raise RuntimeError("T080 fail closed: expected one wrapper and four records")
 kinds=Counter(r.get("policy_target_kind","missing") for r in rows); sources=Counter(r.get("policy_target_source","missing") for r in rows); behavior=Counter(r.get("behavior_action_status","missing") for r in rows); outcomes=Counter(); comps=[]; strata=defaultdict(Counter)
 for r in rows:
  o=r.get("structured_battle_outcome",{}).get("battle_survived",{}); ov="survived" if o.get("status")=="available" and o.get("value") is True else "lost" if o.get("status")=="available" and o.get("value") is False else "unavailable";outcomes[ov]+=1
  t=_stable(r.get("policy_target_action_identity"),"teacher"); b=_stable(r.get("behavior_action"),"behavior") if r.get("behavior_action_status")=="available" else {"status":r.get("behavior_action_status","missing"),"identity":None}; c="same" if t["status"]==b["status"]=="available" and t["identity"]==b["identity"] else "different" if t["status"]==b["status"]=="available" else "unavailable"; comps.append({"example_index":r.get("example_index"),"teacher":t,"behavior":b,"comparison":c})
  sm=r.get("source_metadata",{})
  for k in ("assistance_level","act","room_type","source_kind","distribution_kind"):strata[f"{k}={sm.get(k,'missing')}"][f"compare_{c}"]+=1;strata[f"{k}={sm.get(k,'missing')}"][f"outcome_{ov}"]+=1
 return {"schema_id":REPORT_SCHEMA,"classification":"VALUE_TARGET_SEMANTICS_UNRESOLVED","offline_only":True,"checkpoint":{"path":str(checkpoint),"sha256":cs,"bytes":cb,"metadata":cpmeta},"trainer_input":{"path":str(trainer),"sha256":ts,"bytes":tb,"schema_id":meta.get("policy_target_schema_id"),"format_version":meta.get("format_version"),"record_schema_version":meta.get("decision_record_schema_version"),"record_count":len(rows),"metadata_wrapper_count":wrappers,"provenance":cp},"target_lineage":{"policy_target_kind_counts":dict(kinds),"policy_target_source_counts":dict(sources),"source_behavior_action_status_counts":dict(behavior),"source_outcome_field":"record.structured_battle_outcome.battle_survived","source_outcome_status_counts":dict(outcomes)},"action_comparisons":comps,"strata":dict(strata),"static_call_chain":[{"producer":"src/sts_combat_rl/sim/oracle_teacher_search_guidance.py:_trainer_record_from_teacher_row"},{"producer":"src/sts_combat_rl/sim/oracle_teacher_search_guidance.py:_battle_survived"},{"producer":"src/sts_combat_rl/sim/torch_policy_value.py:_record_targets"},{"consumer":"src/sts_combat_rl/sim/battle_search_v2.py:value_callback/leaf_value_callback","boundary":"after_first_action_from_newly_expanded_node"}],"unresolved":["behavior action unavailable/missing is not inferred","source continuation policy equivalence is not established"]}

def main():
 p=argparse.ArgumentParser();p.add_argument("--checkpoint",type=Path,required=True);p.add_argument("--trainer",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);a=p.parse_args();r=audit(a.checkpoint,a.trainer);a.output_root.mkdir(parents=True,exist_ok=True);rp=a.output_root/"t080-value-target-semantics-audit-v1.json";rp.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n");rh,rb=digest(rp);mp=a.output_root/"t080-retention-manifest-v1.json";m={"schema_id":MANIFEST_SCHEMA,"self_hash_method":"canonical JSON self entry hash is computed with sha256 blank","files":[{"path":str(rp),"sha256":rh,"bytes":rb,"schema_id":REPORT_SCHEMA,"provenance":"exact frozen checkpoint/trainer","regeneration":"this CLI invocation","retention":"immutable T080 evidence","consumer":"T080 review","deletion_condition":"after successor decision"},{"path":str(mp),"sha256":"","bytes":None,"schema_id":MANIFEST_SCHEMA,"provenance":"generated with report","regeneration":"this CLI invocation","retention":"immutable T080 evidence","consumer":"T080 review","deletion_condition":"after successor decision"}]};mp.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n");mh,mb=digest(mp);m["files"][1].update(sha256=mh,bytes=mb);mp.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n");print(json.dumps({"classification":r["classification"],"report":str(rp),"manifest":str(mp)}))
if __name__=="__main__":main()
