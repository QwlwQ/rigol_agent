# NanoDet 远程服务器训练说明

## 1. 目标

使用当前 Rigol 新型号示波器的 26 类 YOLO 数据集，在远程 GPU 服务器训练 NanoDet-Plus，并导出视觉系统可加载的 `screenctrl.onnx`。

训练链路如下：

```text
本地数据检查
→ 上传 train/val 数据和配置
→ 远程安装 NanoDet 与 PyTorch
→ 修改 26 类 YAML 配置
→ 训练并选择最佳权重
→ 导出 ONNX
→ 校验 ONNX 输入输出
→ 下载模型和训练记录
→ 本地部署前验证
```

## 2. 当前本地数据状态

数据根目录：

```text
/home/cjailab/Desktop/RIGOL/datasets
```

已经确认：

```text
原始图片：155 张
YOLO 标签：155 个
类别数量：26
格式错误标签：0
缺失标签：0
```

已经划分：

```text
split/train：124 张图片 + 124 个标签
split/val：31 张图片 + 31 个标签
```

图片和同名标签放在同一个目录中，例如：

```text
split/train/000001.jpg
split/train/000001.txt
```

类别文件：

```text
/home/cjailab/Desktop/RIGOL/datasets/labels/classes.txt
```

当前 26 类顺序为：

```text
0  CH1
1  CH1_select
2  CH2
3  CH2_select
4  CH3
5  CH3_select
6  CH4
7  CH4_select
8  measure
9  Measure_close
10 Vertical
11 Vertical_select
12 Horizontal
13 Horizontal_select
14 Other
15 Other_select
16 Vmax_off
17 Vmax_on
18 Vmin_off
19 Vmin_on
20 Vpp_off
21 Vpp_on
22 Period_off
23 Period_on
24 Frequency_off
25 Frequency_on
```

该顺序是模型与运行系统之间的接口，训练、导出和部署期间不能调整。

## 3. 远程服务器前置检查

向服务器管理员确认：

- SSH 地址、用户名和端口；
- 登录方式；
- GPU 型号和可用显存；
- NVIDIA 驱动状态；
- 是否已经安装 Conda；
- 允许使用的工作目录。

登录示例：

```bash
ssh <用户名>@<服务器地址>
```

非默认端口：

```bash
ssh -p <端口> <用户名>@<服务器地址>
```


检查 GPU：

```bash
nvidia-smi
```

## 4. 上传数据

在服务器建立目录：

```bash
mkdir -p ~/RIGOL_26class
```

在本地真机终端执行：

scp -r /home/cjailab/Desktop/RIGOL/datasets/split \
  root@connect.cqa1.seetacloud.com:~/RIGOL_26class/


```bash
scp -r /home/cjailab/Desktop/RIGOL/datasets/split \
  <用户名>@<服务器地址>:~/RIGOL_26class/

scp /home/cjailab/Desktop/RIGOL/datasets/labels/classes.txt \
  <用户名>@<服务器地址>:~/RIGOL_26class/

scp /home/cjailab/Desktop/RIGOL/datasets/nanodet-torch2-compat.patch \
  <用户名>@<服务器地址>:~/RIGOL_26class/

scp /home/cjailab/Desktop/RIGOL/datasets/nanodet-plus-m_416-rigol7.yml \
  <用户名>@<服务器地址>:~/RIGOL_26class/nanodet-plus-m_416-rigol26.yml
```

如果 SSH 使用非默认端口，`scp` 增加大写参数：

```bash
-P <端口>
```

不要在脚本、仓库或日志中保存 SSH 密码。

## 5. 上传后验证

在服务器执行：

```bash
cd ~/RIGOL_26class

find split/train -maxdepth 1 -name '*.jpg' | wc -l
find split/train -maxdepth 1 -name '[0-9]*.txt' | wc -l
find split/val -maxdepth 1 -name '*.jpg' | wc -l
find split/val -maxdepth 1 -name '[0-9]*.txt' | wc -l
nl -ba classes.txt
```

预期数量：

```text
train 图片：124
train 标签：124
val 图片：31
val 标签：31
classes：26 行
```

## 6. 安装训练环境

### 6.1 创建 Conda 环境

```bash
conda create -n nanodet python=3.10 -y
conda activate nanodet
```

如果 `conda activate` 尚未初始化，可根据实际安装位置加载：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate nanodet
```

### 6.2 安装 PyTorch

历史验证环境为：

```text
Python 3.10
PyTorch 2.1.2
CUDA 12.1
```

服务器驱动支持 CUDA 12.1 时，可执行：

```bash
pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 \
  --index-url https://download.pytorch.org/whl/cu121
```

验证：

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

`torch.cuda.is_available()` 必须为 `True`。如果为 `False`，先处理 PyTorch、CUDA 或驱动问题，不要开始训练。

## 7. 获取 NanoDet 训练源码

当前本地视觉工程只有 C++ ONNX 推理代码，没有 `tools/train.py`。远程服务器需要独立获取 NanoDet：

```bash
cd ~
git clone https://github.com/RangiLyu/nanodet.git
cd nanodet
git rev-parse HEAD
```

保存 `git rev-parse HEAD` 输出的提交号，便于复现。

安装依赖：

```bash
pip install -r requirements.txt
pip install -e .
```

如果该版本仍使用已删除的 `torch._six`，检查：

```bash
rg 'torch._six' nanodet/data/collate.py
```

存在匹配时应用兼容补丁：

```bash
git apply ~/RIGOL_26class/nanodet-torch2-compat.patch
```

补丁的实际修改是将：

```python
from torch._six import string_classes
```

替换为：

```python
string_classes = (str, bytes)
```

如果 NanoDet 当前版本已经修复该问题，不要重复应用补丁。

## 8. 准备 26 类 YAML 配置

训练命令中的 YAML 是 NanoDet 的完整训练配置，负责定义模型、类别、数据路径、训练参数和输出目录。

远程配置文件：

```text
~/RIGOL_26class/nanodet-plus-m_416-rigol26.yml
```

它由旧 7 类配置复制而来，必须修改后才能使用。

### 8.1 输出目录

将 `save_dir` 修改为服务器真实绝对路径，例如：

```yaml
save_dir: /home/<用户名>/RIGOL_26class/runs/nanodet-plus-m_416-rigol26
```

可先使用 `echo $HOME` 确定用户目录。

### 8.2 类别数量

配置中 `head` 和 `aux_head` 各有一处 `num_classes`，都必须设置为：

```yaml
num_classes: 26
```

### 8.3 类别名称

将旧 7 类列表替换为：

```yaml
class_names: &class_names
  - CH1
  - CH1_select
  - CH2
  - CH2_select
  - CH3
  - CH3_select
  - CH4
  - CH4_select
  - measure
  - Measure_close
  - Vertical
  - Vertical_select
  - Horizontal
  - Horizontal_select
  - Other
  - Other_select
  - Vmax_off
  - Vmax_on
  - Vmin_off
  - Vmin_on
  - Vpp_off
  - Vpp_on
  - Period_off
  - Period_on
  - Frequency_off
  - Frequency_on
```

### 8.4 数据路径

训练集：

```yaml
data:
  train:
    name: YoloDataset
    img_path: /home/<用户名>/RIGOL_26class/split/train
    ann_path: /home/<用户名>/RIGOL_26class/split/train
    class_names: *class_names
    input_size: [416, 416]
    keep_ratio: true
```

验证集：

```yaml
  val:
    name: YoloDataset
    img_path: /home/<用户名>/RIGOL_26class/split/val
    ann_path: /home/<用户名>/RIGOL_26class/split/val
    class_names: *class_names
    input_size: [416, 416]
    keep_ratio: true
```

由于图片和标签存放在同一目录，`img_path` 与 `ann_path` 相同。

### 8.5 建议训练参数

第一轮沿用历史验证参数：

```yaml
device:
  gpu_ids: [0]
  workers_per_gpu: 4
  batchsize_per_gpu: 16
  precision: 32

schedule:
  total_epochs: 300
  val_intervals: 10
```

显存不足时先将批大小改为 8；数据加载报错或共享内存不足时，将 workers 改为 2。

训练前检查：

```bash
rg -n 'num_classes|class_names|img_path|ann_path|save_dir' \
  ~/RIGOL_26class/nanodet-plus-m_416-rigol26.yml
```

确认：

- `num_classes` 两处均为 26；
- 类别顺序与 `classes.txt` 完全一致；
- train/val 路径真实存在；
- `save_dir` 可写。

## 9. 启动训练

建议使用 `tmux`，避免 SSH 断开终止训练：

```bash
tmux new -s rigol_train
conda activate nanodet
cd ~/nanodet
```

启动并保存日志：

```bash
python tools/train.py \
  ~/RIGOL_26class/nanodet-plus-m_416-rigol26.yml \
  2>&1 | tee ~/RIGOL_26class/train.log
```

离开但保持训练：按 `Ctrl+B`，再按 `D`。

重新进入：

```bash
tmux attach -t rigol_train
```

训练时重点观察：

```text
loss_qfl
loss_bbox
loss_dfl
mAP
AP50
AP75
```

最佳权重通常位于：

```text
~/RIGOL_26class/runs/nanodet-plus-m_416-rigol26/model_best/nanodet_model_best.pth
```

当前 train/val 来自同一轮连续采集，验证指标可能偏高。正式判断效果时，应另外采集一批未参与训练的新图片。

## 10. 导出 ONNX

```bash
conda activate nanodet
cd ~/nanodet

python tools/export_onnx.py \
  --cfg_path ~/RIGOL_26class/nanodet-plus-m_416-rigol26.yml \
  --model_path ~/RIGOL_26class/runs/nanodet-plus-m_416-rigol26/model_best/nanodet_model_best.pth \
  --out_path ~/RIGOL_26class/screenctrl_26class.onnx
```

视觉端最终使用 ONNX，不直接加载 `.pth` 或 `.ckpt`。

## 11. ONNX 契约检查

模型输入应为：

```text
[1, 3, 416, 416]
```

26 类且 `reg_max=7` 时，最后一维为：

```text
26 + 4 × (7 + 1) = 58
```

预期输出：

```text
[1, 3598, 58]
```

如果类别数量、类别顺序或输出形状不符合预期，不要部署。

## 12. 下载训练产物

回到本地真机终端执行：


```bash
scp <用户名>@<服务器地址>:~/RIGOL_26class/screenctrl_26class.onnx \
  /home/cjailab/Desktop/RIGOL/datasets/training_results/

scp <用户名>@<服务器地址>:~/RIGOL_26class/runs/nanodet-plus-m_416-rigol26/model_best/nanodet_model_best.pth \
  /home/cjailab/Desktop/RIGOL/datasets/training_results/

scp <用户名>@<服务器地址>:~/RIGOL_26class/nanodet-plus-m_416-rigol26.yml \
  /home/cjailab/Desktop/RIGOL/datasets/training_results/

scp <用户名>@<服务器地址>:~/RIGOL_26class/train.log \
  /home/cjailab/Desktop/RIGOL/datasets/training_results/
```

同时保存：

- 最佳 `.pth`；
- 导出的 `.onnx`；
- 最终 YAML；
- `classes.txt`；
- NanoDet Git 提交号；
- 训练日志和评估结果。

## 13. 部署前注意事项

下载后先完成离线检查，不要立即覆盖正在使用的模型。

最终部署至少需要成对替换：

```text
screenctrl.onnx
screenctrl_classes.txt
```

部署前必须备份当前文件，并同步更新：

```text
feedback_config.xml
rigol_agent/knowledge/legacy_mapping.yaml
```

因为新模型的类别 ID 已从旧 7 类变成 26 类。仅替换 ONNX 而不替换类别文件和 ID 映射，会导致错误定位和错误反馈。

## 14. 常见问题

### `torch.cuda.is_available()` 为 False

检查 NVIDIA 驱动、PyTorch CUDA 版本和服务器环境，不要使用 CPU 继续 300 轮训练。

### `No module named torch._six`

应用 `nanodet-torch2-compat.patch`，或将 `string_classes` 改为 `(str, bytes)`。

### CUDA 显存不足

将 `batchsize_per_gpu` 从 16 降至 8 或 4。

### DataLoader 或共享内存错误

将 `workers_per_gpu` 从 4 降至 2 或 1。

### 模型能训练但导出后无法运行

优先检查：

- YAML 两处 `num_classes` 是否均为 26；
- ONNX 输出是否为 `[1,3598,58]`；
- `screenctrl_classes.txt` 是否恰好 26 行；
- 类别顺序是否与训练配置完全一致。
