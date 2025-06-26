# # 浙江大学成绩监控工具
浙大新成绩获取器，解放双手，后台等分

## 功能
- 定期检查新出成绩（支持桌面通知）

- 计算以下指标：

  - 总均绩（GPA）
  - 百分制均分
  - 主修课程均绩（可配置非主修课权重）
  - 主修课程百分制均分

  数据保存为JSON文件

## 使用说明

1.安装依赖：

```bash
pip install -r requirements.txt
```

2.运行程序：

```bash
python test.py
```

## 注意事项

- 程序会在当前目录创建`data/`文件夹存储成绩记录
- 运行首次获取成绩会保存所有课程数据到`data/`目录

## 致谢

爬取部分参考了https://github.com/VVjwell/python_web_crawler 感谢学长
