from pathlib import Path
import csv, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]

def test_queue_filters_needs_review(tmp_path):
    src=tmp_path/'reviewed.csv'; out=tmp_path/'queue.csv'; js=tmp_path/'queue.json'
    fields=['document','property','focus_xml_id','focus_types','focus_label','segment_id','segment_text','previous_segment_text','next_segment_text','relation_review_status','relation_reviewer_note']
    with src.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        w.writerow(dict.fromkeys(fields,'') | {'document':'d1','property':'leco:appealsAgainst','focus_xml_id':'e1','segment_text':'poder para apelaciones','relation_review_status':'needs_review','relation_reviewer_note':'función futura'})
        w.writerow(dict.fromkeys(fields,'') | {'document':'d2','property':'leco:sanctions','focus_xml_id':'e2','relation_review_status':'keep_warning'})
    subprocess.run([sys.executable,str(ROOT/'scripts'/'build_event_typing_review_queue.py'),'--reviews',str(src),'--output',str(out),'--json-output',str(js)],check=True)
    rows=list(csv.DictReader(out.open(encoding='utf-8-sig')))
    assert len(rows)==1
    assert rows[0]['review_issue_category']=='authorized_or_generic_appeal'
    assert rows[0]['typing_review_status']=='pending'
