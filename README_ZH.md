# Mox.moe Epub Manga Repacker

![](https://img.shields.io/badge/python-v3.9-orange) ![](https://img.shields.io/github/license/Haoyi-Han/Moxmoe-Epub-Manga-Repacker)

[English](./README.md) | 中文

## 简介

本项目受已有的两项目（[GeeKaven/vol-moe-comic-scirpt](https://github.com/GeeKaven/vol-moe-comic-scirpt) 和 [yeeac/epub-comic-repacker](https://github.com/yeeac/epub-comic-repacker)）启发，以上项目经测试存在某些问题，故为改善体验，本人用 Python 辅以自身理解作了重构。

本项目设计思路是，首先解包 EPUB 文档（视为 ZIP 压缩包），按照 HTML 名称顺序（为数字）重命名对应的图像文件，再将图像文件打包为 CBZ 文档（同样视为 ZIP 压缩包）。

本项目可以转换单个或多个漫画文件，也可以在转换保存在复杂目录结构中的漫画时，保持其原本的目录结构。

**注意！** 本项目仅适用于从网站 [Kox.moe](https://mox.moe) 或其镜像站下载的 EPUB 文档，从其他源获取的文档如转换失败恕不负责。

**注意！** 本项目可自由使用，只是请不要在本站宣传本项目。本人乐见本项目为大家服务。

如报告问题（Issue），本人会在知识范围内尽力解决。

## 安装 & 用法

用以下命令克隆本项目：

```shell
git clone https://github.com/Haoyi-Han/Moxmoe-Epub-Manga-Repacker.git
cd Moxmoe-Epub-Manga-Repacker
```

将漫画文档（或整个文件夹）复制到该文件夹（`Moxmoe-Epub-Manga-Repacker`）。

**注意！** 因为程序需要按照规则识别文件名，所以转换前请不要更改原文件名！

运行`main.py`脚本：

```shell
python main.py
```

![](./img/2023-04-18.png)

等待程序运行结束。此后您可以进入`output`文件夹检查转换结果。
