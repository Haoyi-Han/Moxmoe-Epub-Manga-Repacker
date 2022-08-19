# Mox.moe Epub Manga Repacker

![](https://img.shields.io/badge/python-v3.9-orange) ![](https://img.shields.io/github/license/Haoyi-Han/Moxmoe-Epub-Manga-Repacker)

English | [中文](./README_ZH.md)

## Introduction
This project is inspired by projects [GeeKaven/vol-moe-comic-scirpt](https://github.com/GeeKaven/vol-moe-comic-scirpt) and [yeeac/epub-comic-repacker](https://github.com/yeeac/epub-comic-repacker). The developer of this project has tested the above projects but failed with unknown reason. So in order to help improve the function of the aforementioned projects, the developer rewrote the program in Python and tried to realise a better experience in use.

This project is designed to unpack the EPUB file (which seen as ZIP file), iterate the HTML files to redefine the order of image files, then repack all the renamed image files as a new CBZ file.

This project allows the user to transfrom manga files which are stored in a certain directory struture. The program will duplicate the structure and build new manga files in the respective location.

**Attention!** This project only fits for manga EPUB files downloaded from websites [Vol.moe](https://vol.moe) or [Mox.moe](https://mox.moe). The developer is not responsible for the failure on EPUB manga downloaded from other sources.

**Attention!** This project is freely used by any Github user following the MIT License, but please don't disseminate this project on Vol.moe or Mox.moe. The developer would appreciate it if you benefit from this project.

The developer would try to do a favor if you raise an issue as well.

## Installation & Usage
Clone this project from Github with commands below:
```shell
git clone https://github.com/Haoyi-Han/Moxmoe-Epub-Manga-Repacker.git
cd Moxmoe-Epub-Manga-Repacker
```

Copy your manga files (or the whole folder) to this directory (`Moxmoe-Epub-Manga-Repacker`) then run `MoeKepub2Cbz.py` script:
```shell
python -m MoeKepub2Cbz.py
```

Wait until the program finishes its task. Then open the `output` folder to check the target files.