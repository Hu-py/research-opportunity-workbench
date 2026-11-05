"""Curated, versioned journal and conference watchlist for source-constrained discovery.

The list is a discovery prior, not an article-quality verdict. CCF labels are
recorded only where the current official CCF 7th-edition directory lists them.
Planning journals use a transparent field-curation label rather than a fake
A/B/C equivalence.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import Boolean, DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from research_workbench.core import Base


CCF_AI = "https://www.ccf.org.cn/Academic_Evaluation/AI/"
CCF_DM = "https://www.ccf.org.cn/Academic_Evaluation/DM_CS/"
CCF_HCI = "https://www.ccf.org.cn/Academic_Evaluation/HCIAndPC/"
CCF_CROSS = "https://www.ccf.org.cn/Academic_Evaluation/Cross_Compre_Emerging/"
CCF_GRAPHICS = "https://www.ccf.org.cn/Academic_Evaluation/CGAndMT/"
CCF_SOFTWARE = "https://www.ccf.org.cn/Academic_Evaluation/TCSE_SS_PDL/"
CCF_NETWORK = "https://www.ccf.org.cn/Academic_Evaluation/CN/"
CCF_SECURITY = "https://www.ccf.org.cn/Academic_Evaluation/NIS/"
CCF_ARCH = "https://www.ccf.org.cn/Academic_Evaluation/ARCH_DCP_SS/"

# name, abbreviation, kind, domain, label, ranking system, source URL,
# aliases, note. All curated rows start enabled; members can pause them.
DEFAULT_SOURCES = [
    # Planning / urban studies: field priorities, deliberately not CCF grades.
    ("Environment and Planning B: Urban Analytics and City Science","EPB","journal","urban_planning","核心","规划与城市计算领域遴选", "https://journals.sagepub.com/home/epb",["Environment and Planning B"],"城市分析、GIS、城市模拟与规划设计分析方法"),
    ("Cities","Cities","journal","urban_planning","核心","规划与城市研究领域遴选","https://www.sciencedirect.com/journal/cities",[],"城市发展、空间治理、城市政策与实证研究"),
    ("Urban Studies","Urban Studies","journal","urban_planning","核心","规划与城市研究领域遴选","https://journals.sagepub.com/home/usj",[],"城市理论、社会空间与城市转型"),
    ("Landscape and Urban Planning","LUP","journal","urban_planning","核心","规划与景观领域遴选","https://www.sciencedirect.com/journal/landscape-and-urban-planning",[],"景观生态、空间规划、城市环境"),
    ("Journal of the American Planning Association","JAPA","journal","urban_planning","核心","规划学科旗舰（非统一ABC分级）","https://www.tandfonline.com/journals/rjpa20",[],"规划理论、规划方法、规划政策与实践"),
    ("Computers, Environment and Urban Systems","CEUS","journal","urban_planning","核心","城市计算领域遴选","https://www.sciencedirect.com/journal/computers-environment-and-urban-systems",["Computers Environment and Urban Systems"],"GIS、城市计算、空间建模与城市系统"),
    ("Journal of Planning Education and Research","JPER","journal","urban_planning","核心","规划学科重点期刊遴选","https://journals.sagepub.com/home/jpe",[],"规划方法、规划理论与规划教育"),
    ("International Journal of Geographical Information Science","IJGIS","journal","gis_spatial","重点","CCF 2026 第七版（数据库/数据挖掘 C）","https://www.tandfonline.com/journals/tgis20",["International Journal of GIS"],"GIScience、空间数据分析与地理信息方法"),
    ("GeoInformatica","GeoInformatica","journal","gis_spatial","重点","CCF 2026 第七版（数据库/数据挖掘 B）","https://link.springer.com/journal/10707",[],"空间数据库、地理计算与地理信息系统"),
    ("Transactions in GIS","TGIS","journal","gis_spatial","重点","地理信息领域重点期刊遴选","https://onlinelibrary.wiley.com/journal/14679671",["Transactions in Geographic Information Systems"],"GIS 方法、空间分析与地理信息应用"),
    ("Journal of Urban Technology","JUT","journal","urban_planning","重点","城市技术领域遴选","https://www.tandfonline.com/journals/cjut20",[],"智慧城市、城市技术及其社会空间影响"),
    ("Journal of Transport Geography","JTG","journal","transportation","重点","交通地理领域重点期刊遴选","https://www.sciencedirect.com/journal/journal-of-transport-geography",[],"交通可达性、交通地理与城市空间"),
    ("Transportation Research Part C: Emerging Technologies","TR-C","journal","transportation","重点","交通技术领域重点期刊遴选","https://www.sciencedirect.com/journal/transportation-research-part-c-emerging-technologies",["Transportation Research Part C"],"智能交通、交通预测、算法与系统"),
    ("Transportation Research Part A: Policy and Practice","TR-A","journal","transportation","重点","交通政策领域重点期刊遴选","https://www.sciencedirect.com/journal/transportation-research-part-a-policy-and-practice",["Transportation Research Part A"],"交通政策、行为与规划实践"),
    ("Sustainable Cities and Society","SCS","journal","urban_planning","重点","可持续城市领域重点期刊遴选","https://www.sciencedirect.com/journal/sustainable-cities-and-society",[],"城市可持续发展、韧性与环境"),
    ("Urban Geography","UG","journal","urban_planning","重点","城市地理领域重点期刊遴选","https://www.tandfonline.com/journals/rurb20",[],"城市空间结构、城市地理与社会空间"),
    ("Applied Geography","AG","journal","gis_spatial","重点","应用地理领域重点期刊遴选","https://www.sciencedirect.com/journal/applied-geography",[],"应用地理、空间决策与地理分析"),
    ("Habitat International","HI","journal","urban_planning","重点","住房与城市发展领域遴选","https://www.sciencedirect.com/journal/habitat-international",[],"住房、城市发展与全球南方城市议题"),
    ("Urban Climate","UC","journal","urban_environment","重点","城市环境领域重点期刊遴选","https://www.sciencedirect.com/journal/urban-climate",[],"城市气候、热环境与气候适应"),
    ("Remote Sensing of Environment","RSE","journal","gis_spatial","重点","遥感领域重点期刊遴选","https://www.sciencedirect.com/journal/remote-sensing-of-environment",[],"遥感观测、地表过程与环境监测"),
    ("ISPRS Journal of Photogrammetry and Remote Sensing","ISPRS JPRS","journal","gis_spatial","重点","摄影测量与遥感领域重点期刊遴选","https://www.sciencedirect.com/journal/isprs-journal-of-photogrammetry-and-remote-sensing",["ISPRS Journal of Photogrammetry and Remote Sensing"],"摄影测量、遥感、三维重建与地理空间AI"),
    ("International Journal of Applied Earth Observation and Geoinformation","IJAEOG","journal","gis_spatial","重点","地理观测领域重点期刊遴选","https://www.sciencedirect.com/journal/international-journal-of-applied-earth-observation-and-geoinformation",["International Journal of Applied Earth Observation and Geoinformation"],"地球观测、遥感与地理信息应用"),
    ("Annals of the American Association of Geographers","Annals AAG","journal","gis_spatial","重点","地理学领域重点期刊遴选","https://www.tandfonline.com/journals/raag20",["Annals of the Association of American Geographers"],"人文地理、自然地理与空间理论"),
    ("Environment and Planning A: Economy and Space","EPA","journal","urban_planning","重点","城市与空间研究领域遴选","https://journals.sagepub.com/home/epn",["Environment and Planning A"],"空间经济、城市政治经济与社会空间"),
    ("International Journal of Urban and Regional Research","IJURR","journal","urban_planning","重点","城市研究领域重点期刊遴选","https://onlinelibrary.wiley.com/journal/14682427",[],"城市与区域研究、空间不平等与城市转型"),

    # AI / machine learning.
    ("Conference on Neural Information Processing Systems","NeurIPS","conference","ai_ml","A","CCF 2026 第七版（人工智能 A）","https://neurips.cc/",["NeurIPS","Advances in Neural Information Processing Systems","Neural Information Processing Systems"],"机器学习、深度学习、基础模型与表示学习"),
    ("International Conference on Machine Learning","ICML","conference","ai_ml","A","CCF 2026 第七版（人工智能 A）","https://icml.cc/",["ICML","Proceedings of the International Conference on Machine Learning"],"机器学习理论、算法与应用"),
    ("AAAI Conference on Artificial Intelligence","AAAI","conference","ai_ml","A","CCF 2026 第七版（人工智能 A）","https://aaai.org/conference/aaai/",["AAAI","Proceedings of the AAAI Conference on Artificial Intelligence"],"人工智能综合研究"),
    ("International Joint Conference on Artificial Intelligence","IJCAI","conference","ai_ml","A","CCF 2026 第七版（人工智能 A）","https://ijcai.org/",["IJCAI","Proceedings of the International Joint Conference on Artificial Intelligence"],"人工智能、知识推理与智能决策"),
    ("International Conference on Learning Representations","ICLR","conference","ai_ml","补充","国际前沿补充观察（CCF第七版未作此项标注）","https://iclr.cc/",["ICLR","Proceedings of the International Conference on Learning Representations"],"深度学习、表征学习与基础模型；单独标记补充来源"),
    ("Journal of Machine Learning Research","JMLR","journal","ai_ml","A","CCF 2026 第七版（人工智能 A）","https://www.jmlr.org/",[],"机器学习理论、算法与系统"),
    ("IEEE Transactions on Pattern Analysis and Machine Intelligence","TPAMI","journal","cv_multimodal","A","CCF 2026 第七版（人工智能 A）","https://www.computer.org/csdl/journal/tp",["IEEE TPAMI"],"模式识别、计算机视觉与机器学习"),
    ("International Journal of Computer Vision","IJCV","journal","cv_multimodal","A","CCF 2026 第七版（人工智能 A）","https://link.springer.com/journal/11263",[],"计算机视觉、视觉表示与场景理解"),
    ("Artificial Intelligence","AI","journal","ai_ml","A","CCF 2026 第七版（人工智能 A）","https://www.sciencedirect.com/journal/artificial-intelligence",[],"人工智能理论与方法"),
    ("Journal of Artificial Intelligence Research","JAIR","journal","ai_ml","B","CCF 2026 第七版（人工智能 B）","https://www.jair.org/",[],"人工智能研究与方法"),
    ("IEEE Transactions on Neural Networks and Learning Systems","TNNLS","journal","ai_ml","B","CCF 2026 第七版（人工智能 B）","https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=5962385",[],"神经网络、深度学习与学习系统"),

    # Data mining / information retrieval / graph and databases.
    ("ACM SIGKDD Conference on Knowledge Discovery and Data Mining","KDD","conference","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://kdd.org/",["KDD","Proceedings of the ACM SIGKDD International Conference on Knowledge Discovery and Data Mining"],"数据挖掘、知识发现与图学习"),
    ("ACM SIGMOD Conference","SIGMOD","conference","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://sigmod.org/",["SIGMOD","Proceedings of the ACM SIGMOD International Conference on Management of Data"],"数据库、数据管理与数据系统"),
    ("IEEE International Conference on Data Engineering","ICDE","conference","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://www.computer.org/conferences/icde",["ICDE","Proceedings of the IEEE International Conference on Data Engineering"],"数据工程与数据管理"),
    ("International ACM SIGIR Conference on Research and Development in Information Retrieval","SIGIR","conference","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://sigir.org/",["SIGIR","Proceedings of the ACM SIGIR Conference on Research and Development in Information Retrieval"],"信息检索、搜索与推荐"),
    ("International Conference on Very Large Data Bases","VLDB","conference","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://vldb.org/",["VLDB","Proceedings of the VLDB Endowment"],"大规模数据管理与数据库系统"),
    ("ACM International Conference on Information and Knowledge Management","CIKM","conference","data_mining","B","CCF 2026 第七版（数据库/数据挖掘 B）","https://www.cikmconference.org/",["CIKM","Proceedings of the ACM International Conference on Information and Knowledge Management"],"信息管理、知识发现与检索"),
    ("ACM International Conference on Web Search and Data Mining","WSDM","conference","data_mining","B","CCF 2026 第七版（数据库/数据挖掘 B）","https://www.wsdm-conference.org/",["WSDM","Proceedings of the ACM International Conference on Web Search and Data Mining"],"Web搜索、数据挖掘与推荐"),
    ("IEEE International Conference on Data Mining","ICDM","conference","data_mining","B","CCF 2026 第七版（数据库/数据挖掘 B）","https://www.data-mining-forum.org/",["ICDM","Proceedings of the IEEE International Conference on Data Mining"],"数据挖掘与机器学习"),
    ("SIAM International Conference on Data Mining","SDM","conference","data_mining","B","CCF 2026 第七版（数据库/数据挖掘 B）","https://www.siam.org/conferences-events/siam-conferences/sdm/",["SDM","Proceedings of the SIAM International Conference on Data Mining"],"数据挖掘、网络科学与应用数学"),
    ("ACM Transactions on Database Systems","TODS","journal","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://dl.acm.org/journal/tods",[],"数据库理论与系统"),
    ("ACM Transactions on Information Systems","TOIS","journal","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://dl.acm.org/journal/tois",[],"信息系统与信息检索"),
    ("IEEE Transactions on Knowledge and Data Engineering","TKDE","journal","data_mining","A","CCF 2026 第七版（数据库/数据挖掘 A）","https://www.computer.org/csdl/journal/tk",[],"知识工程、数据挖掘与数据管理"),

    # Computer vision / multimedia.
    ("IEEE/CVF Conference on Computer Vision and Pattern Recognition","CVPR","conference","cv_multimodal","A","CCF 2026 第七版（人工智能 A）","https://cvpr.thecvf.com/",["CVPR","Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition"],"视觉识别、视觉基础模型与多模态"),
    ("International Conference on Computer Vision","ICCV","conference","cv_multimodal","A","CCF 2026 第七版（人工智能 A）","https://www.thecvf.com/",["ICCV","Proceedings of the IEEE/CVF International Conference on Computer Vision"],"计算机视觉与视觉理解"),
    ("European Conference on Computer Vision","ECCV","conference","cv_multimodal","B","CCF 2026 第七版（人工智能 B）","https://eccv.ecva.net/",["ECCV","Proceedings of the European Conference on Computer Vision"],"计算机视觉与多模态"),
    ("ACM International Conference on Multimedia","ACM MM","conference","graphics_visualization","A","CCF 2026 第七版（图形学与多媒体 A）","https://www.acmmm.org/",["ACM Multimedia","Proceedings of the ACM International Conference on Multimedia"],"多媒体理解、生成与检索"),
    ("ACM Transactions on Graphics","TOG","journal","graphics_visualization","A","CCF 2026 第七版（图形学与多媒体 A）","https://dl.acm.org/journal/tog",[],"计算机图形学与三维表达"),
    ("IEEE Transactions on Visualization and Computer Graphics","TVCG","journal","graphics_visualization","A","CCF 2026 第七版（图形学与多媒体 A）","https://www.computer.org/csdl/journal/tg",[],"可视化、视觉分析与交互"),

    # NLP / language models.
    ("Annual Meeting of the Association for Computational Linguistics","ACL","conference","nlp","A","CCF 2026 第七版（人工智能 A）","https://www.aclweb.org/portal/",["ACL","Proceedings of the Annual Meeting of the Association for Computational Linguistics"],"自然语言处理、语言模型与语言理解"),
    ("Conference on Empirical Methods in Natural Language Processing","EMNLP","conference","nlp","B","CCF 2026 第七版（人工智能 B）","https://emnlp.org/",["EMNLP","Proceedings of the Conference on Empirical Methods in Natural Language Processing"],"NLP实证方法、大语言模型与评测"),
    ("Transactions of the Association for Computational Linguistics","TACL","journal","nlp","B","CCF 2026 第七版（人工智能 B）","https://transacl.org/",["TACL"],"自然语言处理与语言模型研究"),

    # Agents / planning / robotics.
    ("International Conference on Autonomous Agents and Multiagent Systems","AAMAS","conference","agents_robotics","B","CCF 2026 第七版（人工智能 B）","https://aamas.org/",["AAMAS","Proceedings of the International Conference on Autonomous Agents and Multiagent Systems"],"多智能体、自治系统与协同决策"),
    ("International Conference on Automated Planning and Scheduling","ICAPS","conference","agents_robotics","B","CCF 2026 第七版（人工智能 B）","https://icaps-conference.org/",["ICAPS","Proceedings of the International Conference on Automated Planning and Scheduling"],"自动规划、调度与搜索"),
    ("IEEE International Conference on Robotics and Automation","ICRA","conference","agents_robotics","B","CCF 2026 第七版（人工智能 B）","https://www.ieee-ras.org/conferences-workshops/fully-sponsored/icra",["ICRA","Proceedings of the IEEE International Conference on Robotics and Automation"],"机器人、导航与自主决策"),
    ("IEEE/RSJ International Conference on Intelligent Robots and Systems","IROS","conference","agents_robotics","C","CCF 2026 第七版（人工智能 C）","https://www.iros.org/",["IROS","Proceedings of the IEEE/RSJ International Conference on Intelligent Robots and Systems"],"智能机器人与具身系统"),

    # HCI / ubiquitous computing.
    ("ACM Conference on Human Factors in Computing Systems","CHI","conference","hci","A","CCF 2026 第七版（人机交互 A）","https://chi.acm.org/",["CHI","Proceedings of the SIGCHI Conference on Human Factors in Computing Systems"],"人机交互与用户体验"),
    ("ACM Conference on Computer Supported Cooperative Work and Social Computing","CSCW","conference","hci","A","CCF 2026 第七版（人机交互 A）","https://cscw.acm.org/",["CSCW","Proceedings of the ACM Conference on Computer Supported Cooperative Work and Social Computing"],"协同工作、社会计算与人机协作"),
    ("ACM International Joint Conference on Pervasive and Ubiquitous Computing","UbiComp","conference","hci","A","CCF 2026 第七版（人机交互 A）","https://ubicomp.org/",["UbiComp","IMWUT","Proceedings of the ACM on Interactive Mobile Wearable and Ubiquitous Technologies"],"普适计算、移动感知与人机协同"),
    ("ACM Transactions on Computer-Human Interaction","TOCHI","journal","hci","A","CCF 2026 第七版（人机交互 A）","https://dl.acm.org/journal/tochi",[],"人机交互理论与方法"),
    ("ACM International Conference on Intelligent User Interfaces","IUI","conference","hci","B","CCF 2026 第七版（人机交互 B）","https://iui.acm.org/",["IUI","Proceedings of the ACM International Conference on Intelligent User Interfaces"],"智能交互与人机协作"),
    ("ACM Symposium on User Interface Software and Technology","UIST","conference","hci","补充","人机交互前沿补充观察（未作CCF 2026等级标注）","https://uist.acm.org/",["UIST","Proceedings of the ACM Symposium on User Interface Software and Technology"],"用户界面、交互技术与生成式AI界面"),

    # Software engineering / systems.
    ("International Conference on Software Engineering","ICSE","conference","systems_software","A","CCF 2026 第七版（软件工程 A）","https://conf.researchr.org/series/icse",["ICSE","Proceedings of the IEEE/ACM International Conference on Software Engineering"],"软件工程、开发流程与程序分析"),
    ("ACM International Conference on the Foundations of Software Engineering","FSE","conference","systems_software","A","CCF 2026 第七版（软件工程 A）","https://esec-fse.com/",["FSE","ESEC/FSE","Proceedings of the ACM International Conference on the Foundations of Software Engineering"],"软件工程理论、测试与工具"),
    ("International Conference on Automated Software Engineering","ASE","conference","systems_software","A","CCF 2026 第七版（软件工程 A）","https://conf.researchr.org/series/ase",["ASE","Proceedings of the IEEE/ACM International Conference on Automated Software Engineering"],"自动化软件工程与智能编程"),
    ("ACM Symposium on Operating Systems Principles","SOSP","conference","systems_software","A","CCF 2026 第七版（软件系统 A）","https://sosp.org/",["SOSP","Proceedings of the ACM Symposium on Operating Systems Principles"],"操作系统与系统研究"),
    ("USENIX Symposium on Operating Systems Design and Implementation","OSDI","conference","systems_software","A","CCF 2026 第七版（软件系统 A）","https://www.usenix.org/conferences",["OSDI","Proceedings of the USENIX Symposium on Operating Systems Design and Implementation"],"系统设计、分布式系统与基础设施"),

    # Networks / security.
    ("ACM SIGCOMM Conference","SIGCOMM","conference","network_security","A","CCF 2026 第七版（计算机网络 A）","https://conferences.sigcomm.org/",["SIGCOMM","Proceedings of the ACM SIGCOMM Conference"],"网络体系结构与通信系统"),
    ("USENIX Symposium on Networked Systems Design and Implementation","NSDI","conference","network_security","A","CCF 2026 第七版（计算机网络 A）","https://www.usenix.org/conferences",["NSDI","Proceedings of the USENIX Symposium on Networked Systems Design and Implementation"],"网络系统与分布式系统"),
    ("ACM Conference on Computer and Communications Security","CCS","conference","network_security","A","CCF 2026 第七版（网络与信息安全 A）","https://www.sigsac.org/ccs.html",["CCS","Proceedings of the ACM SIGSAC Conference on Computer and Communications Security"],"计算机与通信安全"),
    ("IEEE Symposium on Security and Privacy","S&P","conference","network_security","A","CCF 2026 第七版（网络与信息安全 A）","https://www.ieee-security.org/TC/SP-Index.html",["IEEE S&P","Proceedings of the IEEE Symposium on Security and Privacy"],"系统安全、隐私与可信计算"),

    # Spatial computing conferences.
    ("ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems","SIGSPATIAL","conference","gis_spatial","C","CCF 2026 第七版（交叉/综合/新兴 C）","https://sigspatial.org/",["SIGSPATIAL","ACM SIGSPATIAL","Proceedings of the ACM International Symposium on Advances in Geographic Information Systems"],"空间数据库、地理计算与空间智能"),
    ("International Conference on Spatial Information Theory","COSIT","conference","gis_spatial","C","CCF 2026 第七版（交叉/综合/新兴 C）","https://cosit2024.org/",["COSIT","Proceedings of the International Conference on Spatial Information Theory"],"空间信息理论、认知与地理表示"),
    ("International Symposium on Spatial and Temporal Databases","SSTD","conference","gis_spatial","C","CCF 2026 第七版（数据库/数据挖掘 C）","https://sstd2025.github.io/",["SSTD","Proceedings of the International Symposium on Spatial and Temporal Databases"],"时空数据库与空间查询"),
    ("International World Wide Web Conference","WWW","conference","data_mining","A","CCF 2026 第七版（交叉/综合/新兴 A）","https://www.thewebconf.org/",["WWW","The Web Conference","Proceedings of the ACM Web Conference"],"Web、搜索、推荐、图挖掘与网络科学"),
    ("IEEE/ACM International Symposium on Computer Architecture","ISCA","conference","computer_architecture","A","CCF 2026 第七版（体系结构 A）","https://iscaconf.org/",["ISCA","Proceedings of the ACM/IEEE International Symposium on Computer Architecture"],"计算机体系结构与高性能计算"),
    ("International Conference on Architectural Support for Programming Languages and Operating Systems","ASPLOS","conference","computer_architecture","A","CCF 2026 第七版（体系结构 A）","https://asplos-conference.org/",["ASPLOS","Proceedings of the International Conference on Architectural Support for Programming Languages and Operating Systems"],"体系结构、操作系统与编程语言交叉"),
    ("IEEE International Symposium on High Performance Computer Architecture","HPCA","conference","computer_architecture","A","CCF 2026 第七版（体系结构 A）","https://hpca-conf.org/",["HPCA","Proceedings of the IEEE International Symposium on High Performance Computer Architecture"],"高性能计算机体系结构"),
    ("IEEE/ACM International Symposium on Microarchitecture","MICRO","conference","computer_architecture","A","CCF 2026 第七版（体系结构 A）","https://www.microarch.org/",["MICRO","Proceedings of the IEEE/ACM International Symposium on Microarchitecture"],"微体系结构与处理器设计"),
    ("ACM Symposium on Theory of Computing","STOC","conference","theory_algorithms","A","CCF 2026 第七版（计算机科学理论 A）","https://acm-stoc.org/",["STOC","Proceedings of the ACM Symposium on Theory of Computing"],"计算理论与算法基础"),
    ("ACM-SIAM Symposium on Discrete Algorithms","SODA","conference","theory_algorithms","A","CCF 2026 第七版（计算机科学理论 A）","https://www.siam.org/conferences-events/siam-conferences/soda/",["SODA","Proceedings of the ACM-SIAM Symposium on Discrete Algorithms"],"离散算法与组合优化"),
    ("IEEE Symposium on Foundations of Computer Science","FOCS","conference","theory_algorithms","A","CCF 2026 第七版（计算机科学理论 A）","https://focs.computer.org/",["FOCS","Proceedings of the IEEE Symposium on Foundations of Computer Science"],"计算机科学理论与算法"),
    ("Robotics: Science and Systems","RSS","conference","agents_robotics","补充","国际机器人旗舰补充观察（非CCF 2026标注）","https://roboticsconference.org/",["RSS","Robotics Science and Systems"],"机器人学习、具身智能与自主系统"),
    ("Conference on Robot Learning","CoRL","conference","agents_robotics","补充","机器人学习前沿补充观察（非CCF 2026标注）","https://www.robot-learning.org/",["CoRL","Conference on Robot Learning"],"机器人学习、世界模型与具身策略"),
    ("Conference on Language Modeling","COLM","conference","nlp","补充","语言模型前沿补充观察（非CCF 2026标注）","https://colmweb.org/",["COLM","Conference on Language Modeling"],"大语言模型、语言建模与评测"),
    ("IEEE Transactions on Intelligent Transportation Systems","TITS","journal","transportation","B","CCF 2026 第七版（交叉/综合/新兴 B）","https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=6979",["IEEE T-ITS"],"智能交通系统、交通预测与控制"),
    ("IEEE Transactions on Geoscience and Remote Sensing","TGRS","journal","gis_spatial","B","CCF 2026 第七版（交叉/综合/新兴 B）","https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=36",["IEEE TGARS"],"遥感、地球观测与空间智能"),
    ("IEEE Transactions on Robotics","T-RO","journal","agents_robotics","B","CCF 2026 第七版（交叉/综合/新兴 B）","https://www.ieee-ras.org/publications/t-ro",["IEEE T-RO"],"机器人理论、运动规划与自主系统"),
    ("IEEE Transactions on Automation Science and Engineering","T-ASE","journal","agents_robotics","B","CCF 2026 第七版（交叉/综合/新兴 B）","https://www.ieee-ras.org/publications/t-ase",["IEEE T-ASE"],"自动化科学、智能调度与机器人系统"),

    # Team-adjacent applied research: health, heritage, water, disaster and fire.
    ("Health and Place","Health & Place","journal","urban_health","核心","健康地理与城市健康领域遴选","https://www.sciencedirect.com/journal/health-and-place",["Health & Place"],"健康地理、健康公平、建成环境与健康"),
    ("Social Science and Medicine","SSM","journal","urban_health","重点","健康社会科学领域遴选","https://www.sciencedirect.com/journal/social-science-and-medicine",["Social Science & Medicine"],"健康社会决定因素、健康不平等与社会空间"),
    ("Journal of Transport and Health","JTH","journal","urban_health","重点","交通健康交叉领域遴选","https://www.sciencedirect.com/journal/journal-of-transport-and-health",["Journal of Transport & Health"],"交通可达性、出行行为与健康"),
    ("Journal of Cultural Heritage","JCH","journal","heritage","核心","文化遗产研究领域遴选","https://www.sciencedirect.com/journal/journal-of-cultural-heritage",[],"文化遗产保护、风险评估与数字化"),
    ("International Journal of Heritage Studies","IJHS","journal","heritage","重点","遗产研究领域遴选","https://www.tandfonline.com/journals/rjhs20",[],"遗产价值、保护治理与社会文化研究"),
    ("Heritage Science","Heritage Science","journal","heritage","重点","遗产科学领域遴选","https://heritagesciencejournal.springeropen.com/",[],"遗产科学、数字遗产与多学科保护"),
    ("International Journal of Disaster Risk Reduction","IJDRR","journal","water_disaster","核心","灾害风险研究领域遴选","https://www.sciencedirect.com/journal/international-journal-of-disaster-risk-reduction",[],"灾害风险、应急管理、韧性与风险治理"),
    ("Natural Hazards","Natural Hazards","journal","water_disaster","重点","自然灾害研究领域遴选","https://link.springer.com/journal/11069",[],"自然灾害、风险评估与减灾"),
    ("Journal of Hydrology","JH","journal","water_disaster","核心","水文水资源领域遴选","https://www.sciencedirect.com/journal/journal-of-hydrology",[],"水文模拟、洪涝过程与水系统"),
    ("Water Resources Research","WRR","journal","water_disaster","重点","水资源研究领域遴选","https://agupubs.onlinelibrary.wiley.com/journal/19447973",[],"水资源系统、水文过程与模型"),
    ("Water Research","Water Research","journal","water_disaster","重点","水环境领域遴选","https://www.sciencedirect.com/journal/water-research",[],"水环境、污染过程与水系统治理"),
    ("Fire Safety Journal","FSJ","journal","water_disaster","重点","消防安全领域遴选","https://www.sciencedirect.com/journal/fire-safety-journal",[],"火灾科学、消防安全与风险控制"),
    ("Safety Science","Safety Science","journal","water_disaster","重点","安全科学领域遴选","https://www.sciencedirect.com/journal/safety-science",[],"安全风险、应急管理与系统安全"),
    ("Reliability Engineering and System Safety","RESS","journal","water_disaster","重点","系统可靠性领域遴选","https://www.sciencedirect.com/journal/reliability-engineering-and-system-safety",["Reliability Engineering & System Safety"],"复杂系统可靠性、风险与安全决策"),
]


def now():
    return datetime.now(timezone.utc)


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _source_id(value):
    raw = str(value or "").strip().rstrip("/")
    token = raw.rsplit("/", 1)[-1]
    return token if re.fullmatch(r"S\d+", token) else ""


class ResearchSource(Base):
    __tablename__ = "research_sources"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(260), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(60), default="")
    kind: Mapped[str] = mapped_column(String(20), default="journal")
    domain: Mapped[str] = mapped_column(String(40), default="urban_planning", index=True)
    rank_label: Mapped[str] = mapped_column(String(24), default="重点")
    ranking_system: Mapped[str] = mapped_column(String(180), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    openalex_source_id: Mapped[str] = mapped_column(String(80), default="")
    resolution_status: Mapped[str] = mapped_column(String(24), default="unresolved")
    openalex_type: Mapped[str] = mapped_column(String(40), default="")
    resolution_note: Mapped[str] = mapped_column(String(300), default="")
    created_by: Mapped[str] = mapped_column(String(48), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def _aliases(row):
    try:
        values = json.loads(row.aliases_json or "[]")
        return [x for x in values if isinstance(x, str)]
    except (TypeError, ValueError):
        return []


def source_dict(row):
    return {
        "id": row.id, "name": row.name, "abbreviation": row.abbreviation,
        "kind": row.kind, "domain": row.domain, "rank_label": row.rank_label,
        "ranking_system": row.ranking_system, "source_url": row.source_url,
        "aliases": _aliases(row), "notes": row.notes, "enabled": row.enabled,
        "is_seed": row.is_seed, "openalex_source_id": row.openalex_source_id,
        "resolution_status": row.resolution_status,
        "openalex_type": row.openalex_type, "resolution_note": row.resolution_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def seed_default_sources(db):
    """Idempotently seed the curated public source catalogue."""
    added = 0
    for (name, abbr, kind, domain, label, system, url, aliases, notes) in DEFAULT_SOURCES:
        ident = "src_" + hashlib.sha256((kind + "|" + name).encode()).hexdigest()[:24]
        if db.get(ResearchSource, ident):
            continue
        db.add(ResearchSource(
            id=ident, name=name, abbreviation=abbr, kind=kind, domain=domain,
            rank_label=label, ranking_system=system, source_url=url,
            aliases_json=json.dumps(aliases, ensure_ascii=False), notes=notes,
            enabled=True, is_seed=True,
        ))
        added += 1
    if added:
        db.commit()
    return added


def list_sources(db, *, enabled_only=False, domain="", kind=""):
    query = select(ResearchSource)
    if enabled_only:
        query = query.where(ResearchSource.enabled.is_(True))
    if domain:
        query = query.where(ResearchSource.domain == domain)
    if kind:
        query = query.where(ResearchSource.kind == kind)
    rows = db.scalars(query.order_by(
        ResearchSource.domain.asc(), ResearchSource.kind.asc(),
        ResearchSource.name.asc()
    )).all()
    return [source_dict(row) for row in rows]


def create_source(db, payload, actor=""):
    name = str(payload.get("name", "")).strip()
    abbreviation = str(payload.get("abbreviation", "")).strip()
    kind = payload.get("kind", "journal")
    domain = payload.get("domain", "urban_planning")
    if not 3 <= len(name) <= 260:
        raise ValueError("来源名称需要 3–260 个字符")
    if kind not in ("journal", "conference"):
        raise ValueError("来源类型只能是期刊或会议")
    if not re.fullmatch(r"[a-z0-9_]{2,40}", str(domain)):
        raise ValueError("领域标识格式无效")
    if any(_norm(name) == _norm(x.name) for x in db.scalars(select(ResearchSource)).all()):
        raise ValueError("该期刊/会议已存在")
    source_url=str(payload.get("source_url", "")).strip()
    if source_url and not source_url.startswith("https://"):
        raise ValueError("来源主页必须使用 HTTPS 地址")
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list) or len(aliases) > 12 or any(
        not isinstance(x, str) or not x.strip() for x in aliases
    ):
        raise ValueError("别名最多 12 项，且不能为空")
    row = ResearchSource(
        id="src_" + uuid.uuid4().hex[:24], name=name,
        abbreviation=abbreviation[:60], kind=kind, domain=domain,
        rank_label=str(payload.get("rank_label", "自定义"))[:24],
        ranking_system=str(payload.get("ranking_system", "团队自定义来源"))[:180],
        source_url=source_url[:1200],
        aliases_json=json.dumps(list(dict.fromkeys(x.strip()[:180] for x in aliases)), ensure_ascii=False),
        notes=str(payload.get("notes", ""))[:1000],
        enabled=bool(payload.get("enabled", True)), created_by=actor,
    )
    db.add(row)
    db.commit()
    return source_dict(row)


def update_source(db, ident, values):
    row = db.get(ResearchSource, ident)
    if row is None:
        raise ValueError("关注来源不存在")
    for key in ("name", "abbreviation", "kind", "domain", "rank_label",
                "ranking_system", "source_url", "notes", "enabled"):
        if key in values:
            value = values[key]
            if key == "name" and (not isinstance(value, str) or not 3 <= len(value.strip()) <= 260):
                raise ValueError("来源名称需要 3–260 个字符")
            if key == "kind" and value not in ("journal", "conference"):
                raise ValueError("来源类型只能是期刊或会议")
            if key == "domain" and not re.fullmatch(r"[a-z0-9_]{2,40}", str(value)):
                raise ValueError("领域标识格式无效")
            if key == "name":
                duplicate=db.scalars(select(ResearchSource).where(
                    ResearchSource.id!=ident)).all()
                if any(_norm(value)==_norm(x.name) for x in duplicate):
                    raise ValueError("该期刊/会议名称已被其他来源使用")
            if key == "source_url" and value and not str(value).startswith("https://"):
                raise ValueError("来源主页必须使用 HTTPS 地址")
            setattr(row, key, value.strip() if isinstance(value, str) else bool(value))
    if "aliases" in values:
        aliases = values["aliases"]
        if not isinstance(aliases, list) or len(aliases) > 12 or any(
            not isinstance(x, str) or not x.strip() for x in aliases
        ):
            raise ValueError("别名最多 12 项，且不能为空")
        row.aliases_json = json.dumps(list(dict.fromkeys(x.strip()[:180] for x in aliases)), ensure_ascii=False)
    if "openalex_source_id" in values:
        ident_value = _source_id(values["openalex_source_id"])
        if not ident_value:
            raise ValueError("OpenAlex 来源 ID 格式应为 S123456 或完整 OpenAlex Source URL")
        row.openalex_source_id = ident_value
        row.resolution_status = "resolved"
        row.resolution_note = "管理员手动指定来源 ID"
    elif any(k in values for k in ("name", "abbreviation", "aliases")):
        row.openalex_source_id = ""
        row.openalex_type = ""
        row.resolution_status = "unresolved"
        row.resolution_note = "来源名称或别名已修改，等待重新核验"
    row.updated_at = now()
    db.commit()
    return source_dict(row)


def match_source_rows(db, names=None, *, enabled_only=True):
    query = select(ResearchSource)
    if enabled_only:
        query = query.where(ResearchSource.enabled.is_(True))
    rows = db.scalars(query).all()
    if not names:
        return rows
    wanted = {_norm(x) for x in names if isinstance(x, str) and x.strip()}
    return [row for row in rows if wanted.intersection(
        {_norm(row.name), _norm(row.abbreviation), *(_norm(x) for x in _aliases(row))}
    )]


def _openalex_source_candidates(row, client):
    # Search by canonical name and short name only. Aliases are used for
    # exact validation, not as an unbounded sequence of extra API requests.
    terms = [row.name, row.abbreviation]
    exact_names = [row.name, row.abbreviation] + _aliases(row)
    for term in [x for x in terms if x]:
        params = {"search": term, "per-page": 20}
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        if os.getenv("OPENALEX_MAILTO"):
            params["mailto"] = os.environ["OPENALEX_MAILTO"]
        response = client.get("https://api.openalex.org/sources", params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
        exact = []
        wanted = {_norm(x) for x in exact_names if x}
        for item in results:
            names = [item.get("display_name", ""), item.get("abbreviated_title", "")]
            names.extend(item.get("alternate_titles") or [])
            if not wanted.intersection({_norm(x) for x in names if x}):
                continue
            source_type = str(item.get("type") or "").lower()
            if row.kind == "journal" and source_type != "journal":
                continue
            if row.kind == "conference" and source_type not in ("conference", "journal"):
                continue
            source_ident = _source_id(item.get("id"))
            if source_ident:
                exact.append((item, source_ident))
        if exact:
            unique = {ident: item for item, ident in exact}
            return [(item, ident) for ident, item in unique.items()]
    return []


def resolve_sources(db, source_ids=None, *, force=False, client=None, max_items=100):
    """Resolve canonical names to exact OpenAlex Source IDs; never fuzzy-guess."""
    query = select(ResearchSource)
    if source_ids:
        query = query.where(ResearchSource.id.in_(source_ids))
    else:
        query = query.where(ResearchSource.enabled.is_(True))
    rows = db.scalars(query.order_by(ResearchSource.name.asc()).limit(max_items)).all()
    own = client is None
    http = client or httpx.Client(timeout=25, headers={
        "User-Agent": "research-opportunity-workbench/0.2"
    })
    summary = {"checked": 0, "resolved": 0, "ambiguous": 0, "not_found": 0, "errors": 0}
    try:
        for row in rows:
            if row.resolution_status == "resolved" and row.openalex_source_id and not force:
                summary["resolved"] += 1
                continue
            if row.resolution_status in ("not_found", "ambiguous", "error") and not force:
                summary[row.resolution_status if row.resolution_status in summary else "errors"] += 1
                continue
            summary["checked"] += 1
            try:
                matches = _openalex_source_candidates(row, http)
                if len(matches) == 1:
                    item, ident = matches[0]
                    row.openalex_source_id = ident
                    row.openalex_type = str(item.get("type") or "")
                    row.resolution_status = "resolved"
                    row.resolution_note = "OpenAlex 来源名称/别名精确匹配"
                    summary["resolved"] += 1
                elif len(matches) > 1:
                    row.openalex_source_id = ""
                    row.openalex_type = ""
                    row.resolution_status = "ambiguous"
                    row.resolution_note = "存在多个精确匹配来源，需人工指定 OpenAlex ID"
                    summary["ambiguous"] += 1
                else:
                    row.openalex_source_id = ""
                    row.openalex_type = ""
                    row.resolution_status = "not_found"
                    row.resolution_note = "OpenAlex 未找到名称/别名精确匹配；未采用模糊匹配"
                    summary["not_found"] += 1
            except (httpx.HTTPError, ValueError, KeyError):
                row.resolution_status = "error"
                row.resolution_note = "OpenAlex 来源核验请求失败"
                summary["errors"] += 1
            row.updated_at = now()
            db.commit()
    finally:
        if own:
            http.close()
    return summary


def resolve_enabled_source_ids(db, names=None, *, client=None, force=False):
    """Return only exact, resolved IDs. Empty means strict source filtering must stop."""
    rows = match_source_rows(db, names, enabled_only=True)
    if not rows:
        return [], {"checked": 0, "resolved": 0, "ambiguous": 0,
                    "not_found": 0, "errors": 0, "matched_sources": 0}
    summary = resolve_sources(db, [row.id for row in rows], force=force, client=client)
    ids = [row.openalex_source_id for row in rows
           if row.resolution_status == "resolved" and row.openalex_source_id]
    return list(dict.fromkeys(ids)), {**summary, "matched_sources": len(rows)}



DIRECT_SOURCE_DOMAINS = {
    "urban_planning", "urban_environment", "transportation", "gis_spatial",
    "urban_health", "heritage", "water_disaster",
}
METHOD_SOURCE_DOMAINS = {
    "gis_spatial", "ai_ml", "data_mining", "cv_multimodal", "nlp",
    "agents_robotics", "hci", "graphics_visualization", "systems_software",
    "network_security", "computer_architecture", "theory_algorithms",
}

def resolve_source_ids_by_mode(db, *, client=None, force=False):
    """Split source whitelist into domain evidence and transferable CS methods."""
    all_ids, summary = resolve_enabled_source_ids(db, client=client, force=force)
    if not all_ids:
        return {"direct": [], "method": []}, summary
    rows = db.scalars(select(ResearchSource).where(
        ResearchSource.openalex_source_id.in_(all_ids))).all()
    direct = [x.openalex_source_id for x in rows
              if x.domain in DIRECT_SOURCE_DOMAINS]
    method = [x.openalex_source_id for x in rows
              if x.domain in METHOD_SOURCE_DOMAINS]
    return {
        "direct": list(dict.fromkeys(direct)),
        "method": list(dict.fromkeys(method)),
    }, {**summary, "direct_sources": len(direct), "method_sources": len(method)}


def resolve_sources_task(factory, source_ids=None, force=False):
    with factory() as db:
        return resolve_sources(db, source_ids, force=force)


def domain_counts(db):
    enabled=db.query(ResearchSource).filter(ResearchSource.enabled.is_(True)).all()
    resolved=[x for x in enabled if x.resolution_status=="resolved" and x.openalex_source_id]
    direct=[x for x in enabled if x.domain in DIRECT_SOURCE_DOMAINS]
    method=[x for x in enabled if x.domain in METHOD_SOURCE_DOMAINS]
    return {
        "total": db.query(ResearchSource).count(),
        "enabled": len(enabled),
        "resolved": len(resolved),
        "unresolved": len(enabled)-len(resolved),
        "direct_enabled":len(direct),
        "direct_resolved":sum(x.resolution_status=="resolved" and bool(x.openalex_source_id) for x in direct),
        "method_enabled":len(method),
        "method_resolved":sum(x.resolution_status=="resolved" and bool(x.openalex_source_id) for x in method),
    }


def delete_source(db, ident):
    row=db.get(ResearchSource,ident)
    if row is None:
        raise ValueError("关注来源不存在")
    # Preserve auditability and prior paper provenance: deletion is a soft disable.
    row.enabled=False
    row.updated_at=now()
    db.commit()
    return source_dict(row)
