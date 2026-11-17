from pathlib import Path
from rigol_agent.agent import Agent
from rigol_agent.knowledge import Knowledge
from rigol_agent.planner import Planner, TaskValidator
from rigol_agent.repository import TaskRepository
from rigol_agent.models import AgentError
from task.legacy_adapter import LegacyTaskAdapter
from rigol_agent.ros2_executor import ExecutionResult, Ros2TaskExecutor

def make(tmp_path):
 k=Knowledge(Path('knowledge/demo')); p=Planner(k); v=TaskValidator(k); return Agent(p,v,TaskRepository(tmp_path)),p,v

def test_click(tmp_path):
 a,_,_=make(tmp_path); t=a.planner.build(a.planner.parse('点击 CH2',[])); assert len(t.tasks[0].steps)==1 and t.tasks[0].steps[0].component=='CH2'
def test_measure(tmp_path):
 a,_,_=make(tmp_path); t=a.planner.build(a.planner.parse('测量 CH2 的电压峰峰值',[])); assert [s.component for s in t.tasks[0].steps]==['CH2','Measure','Peak-to-Peak','Close-Measurement']
def test_multiple(tmp_path):
 a,_,_=make(tmp_path); t=a.planner.build(a.planner.parse('测量 CH2 的电压峰峰值，然后测量 CH1 的频率，最后切换到 CH2',[])); assert len(t.tasks)==3
def test_alias(tmp_path):
 a,_,_=make(tmp_path); t=a.planner.build(a.planner.parse('测量第二通道的峰峰电压',[])); assert t.tasks[0].parameters['channel']=='CH2'
def test_missing(tmp_path):
 a,_,_=make(tmp_path); assert 'channel' in a.handle('测量电压峰峰值')
def test_illegal_component(tmp_path):
 a,_,_=make(tmp_path); assert '不支持组件' in a.handle('测量 CH5 的频率')
def test_multiturn(tmp_path):
 a,_,_=make(tmp_path); assert 'CH2' in a.handle('测量 CH2 的电压峰峰值'); assert 'CH1' in a.handle('再测量 CH1 的频率')
def test_json_roundtrip_and_tamper(tmp_path):
 a,p,v=make(tmp_path); t=v.validate(p.build(p.parse('测量 CH2 的电压峰峰值',[]))); path,loaded=TaskRepository(tmp_path).save(t); assert loaded.task_id==t.task_id; d=loaded.model_copy(update={'tasks':[loaded.tasks[0].model_copy(update={'steps':[]})]}); 
 try: v.validate(d); assert False
 except ValueError: pass

def test_close_resets_category(tmp_path):
    a,p,v=make(tmp_path)
    proposal=p.parse('先测量 CH1 的频率，再测量 CH2 的频率',[])
    task=v.validate(p.build(proposal))
    assert [s.component for s in task.tasks[0].steps] == ['CH1','Measure','Horizontal','Frequency','Close-Measurement']
    assert [s.component for s in task.tasks[1].steps] == ['CH2','Measure','Horizontal','Frequency','Close-Measurement']

def test_verified_legacy_component_ids(tmp_path):
    _,p,v=make(tmp_path)
    adapter=LegacyTaskAdapter()
    proposal=p.parse('点击 CH1，然后点击 CH4，最后点击 Measure',[])
    exported=adapter.convert(v.validate(p.build(proposal)))['taskList']
    assert [(item['targetName'],item['name_id']) for item in exported] == [
        ('SCREEN_CTRL(1):CH1(0)',0),
        ('SCREEN_CTRL(1):CH4(6)',6),
        ('SCREEN_CTRL(1):measure(8)',8),
    ]

def test_verified_vmax_id(tmp_path):
    _,p,v=make(tmp_path)
    adapter=LegacyTaskAdapter()
    proposal=p.parse('点击最大值',[])
    exported=adapter.convert(v.validate(p.build(proposal)))['taskList']
    assert exported[0]['targetName'] == 'SCREEN_CTRL(1):Vmax_off(16)'
    assert exported[0]['name_id'] == 16

def test_provisional_component_cannot_be_exported(tmp_path):
    _,p,v=make(tmp_path)
    task=v.validate(p.build(p.parse('点击幅度值',[])))
    try:
        LegacyTaskAdapter().convert(task)
        assert False
    except AgentError as exc:
        assert '临时值' in str(exc)

def test_save_pending_accepts_built_task(tmp_path):
    a,_,_=make(tmp_path)
    a.handle('点击 CH1')
    answer=a.save_pending()
    assert '任务已保存' in answer
    assert len(list(tmp_path.glob('*.json'))) == 1

def test_rigol_real_measurement_exports_current_ids(tmp_path):
    k=Knowledge(Path('knowledge/rigol_real')); p=Planner(k); v=TaskValidator(k)
    task=v.validate(p.build(p.parse('测量 CH2 的频率',[])))
    exported=LegacyTaskAdapter().convert(task)['taskList']
    assert [(item['name_id'],item['targetName']) for item in exported] == [
        (2,'SCREEN_CTRL(1):CH2(2)'),
        (8,'SCREEN_CTRL(1):measure(8)'),
        (12,'SCREEN_CTRL(1):Horizontal(12)'),
        (24,'SCREEN_CTRL(1):Frequency_off(24)'),
        (9,'SCREEN_CTRL(1):Measure_close(9)'),
    ]

def test_ros2_executor_rejects_non_click_payload():
    try:
        Ros2TaskExecutor.validate_payload({'taskList':[{'taskType':1,'category_id':1,'name_id':0,'useCord':0}]})
        assert False
    except AgentError as exc:
        assert 'taskType=0' in str(exc)

def test_execute_pending_uses_legacy_payload(tmp_path):
    class FakeExecutor:
        def execute(self,payload,progress=None,status=None):
            assert [x['name_id'] for x in payload['taskList']] == [2]
            return ExecutionResult(1,1)
    k=Knowledge(Path('knowledge/rigol_real')); p=Planner(k); v=TaskValidator(k)
    a=Agent(p,v,TaskRepository(tmp_path))
    a.handle('点击 CH2')
    assert a.execute_pending(LegacyTaskAdapter(),FakeExecutor()) == '任务执行完成：1/1 步'
