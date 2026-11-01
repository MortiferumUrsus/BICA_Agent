from context_memory.strong_report import matched_comparison


def test_model_comparison_uses_shared_ids_only():
    def row(identity,profile,correct):
        return {'id':identity,'profile':profile,'dataset':'babilong','mode':'summary','correct':correct}
    previous=[row('a','old',False),row('b','old',True),row('c','old',True)]
    current=[row('a','new',True)]
    result=matched_comparison(current,previous,'new','old','babilong','summary')
    assert result['n']==1 and result['ids']==['a']
    assert result['old_correct']==0 and result['new_correct']==1
    assert result['delta_accuracy']==1
    assert matched_comparison(current,previous,'absent','old','babilong','summary') is None
