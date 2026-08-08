from core.nms import global_nms

def test_nms_no_overlap():
    dets = [{"bbox":[0,0,10,10],"confidence":0.9,"class":0,"class_name":"a"},
            {"bbox":[100,100,110,110],"confidence":0.8,"class":0,"class_name":"a"}]
    assert len(global_nms(dets, 0.5)) == 2

def test_nms_high_overlap_removes_low_conf():
    dets = [{"bbox":[0,0,10,10],"confidence":0.9,"class":0,"class_name":"a"},
            {"bbox":[1,1,11,11],"confidence":0.5,"class":0,"class_name":"a"}]
    result = global_nms(dets, 0.5)
    assert len(result) == 1 and result[0]["confidence"] == 0.9

def test_nms_empty():
    assert global_nms([], 0.5) == []

def test_nms_different_class_not_suppressed():
    dets = [{"bbox":[0,0,10,10],"confidence":0.9,"class":0,"class_name":"a"},
            {"bbox":[1,1,11,11],"confidence":0.5,"class":1,"class_name":"b"}]
    assert len(global_nms(dets, 0.5)) == 2
