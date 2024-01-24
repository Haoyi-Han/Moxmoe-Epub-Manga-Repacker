# Mox.moe Epub Manga Repacker

![](https://img.shields.io/badge/python-v3.10-orange) ![](https://img.shields.io/github/license/Haoyi-Han/Moxmoe-Epub-Manga-Repacker)

[English](./README.md) | 中文

## 声明

**注意！** 本项目不提供漫画文档下载服务，你仍然需要通过网站提供的免费或付费服务下载漫画。

**注意！** 本项目仅适用于从网站 [Kox.moe](https://mox.moe) 或其镜像站下载的 EPUB 文档，从其他源获取的文档如转换失败恕不负责。

**注意！** 本项目无任何广告盈利，任何人可免费自由使用，只是请不要在漫画网站宣传本项目，以避免不必要的法律纠纷。本人乐见本项目为大家服务。

如在使用中遇到问题请提交 Issue，本人会在知识范围内尽力解决。

## 原理

本项目设计思路是，首先将 EPUB 文档视为 ZIP 压缩包解包，按照 HTML 名称中的数字顺序重命名每个页面包含的图像文件，再将图像文件打包为 CBZ 文档。

本项目可以转换单个或多个漫画文件，也可以在转换保存在复杂目录结构中的漫画时，保持其原本的目录结构。

## 用法

用以下命令克隆本项目：

```shell
git clone https://github.com/Haoyi-Han/Moxmoe-Epub-Manga-Repacker.git
cd Moxmoe-Epub-Manga-Repacker
```

项目配置文件格式形如：

```toml
[DEFAULT]
InputDir =  "your input folder path"
OutputDir = "your output folder path"
CacheDir =  "your cache folder path"
Exclude = [folders & files to exclude in the paths you provide]
```

将漫画文档（或整个文件夹）复制到该 `InputDir` 指向的文件夹。**注意！** 子文件夹和子文件的命名请避免使用除常见符号、字母、数字、汉字以外的特殊 Unicode 字符。

运行`main.py`脚本：

```shell
python main.py
```

程序运行时截图效果如下（并非最新版本，供大致参考）。

![](./img/2023-04-18.png)

等待程序运行结束。此后您可以进入 `OutputDir` 指向的文件夹，检查转换结果。

## 构建

推荐使用 `Nuitka` 构建可执行文件应用程序。Windows 平台下请运行 `make.ps1 build`，Unix 平台下请运行 `make build`，随后在 `build` 文件夹可以得到构建后的单文件程序。

你可以通过 `make.ps1 help` 或 `make help` 来查看支持的命令帮助。

为保证该程序正常运行，你需要在可执行文件所在目录下建立 `config.toml` 配置文件，并完善配置文件中指定目录的路径。

对于 Windows 平台，作为一个可选选项，如果你希望程序运行时在任务栏同步显示进度，那么你需要将仓库中的 `tl.tlb` 文件复制到可执行文件所在目录，该文件是微软控制任务栏行为的链接库文件，你也可以手动下载。

## Stargazers over time

[![Stargazers over time](https://starchart.cc/Haoyi-Han/Moxmoe-Epub-Manga-Repacker.svg)](https://starchart.cc/Haoyi-Han/Moxmoe-Epub-Manga-Repacker)

## 鸣谢（项目灵感来源）

[GeeKaven/vol-moe-comic-scirpt](https://github.com/GeeKaven/vol-moe-comic-scirpt)：主要代码逻辑参考

[yeeac/epub-comic-repacker](https://github.com/yeeac/epub-comic-repacker)：辅助代码逻辑参考

[Zeal-L/BiliBili-Manga-Downloader](https://github.com/Zeal-L/BiliBili-Manga-Downloader)： `ComicInfo.xml` 编写参考