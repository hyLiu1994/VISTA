# VISTA: Knowledge-Driven Interpretable Vessel Trajectory Imputation via Large Language Models
This is the official implementation of the paper "VISTA: Knowledge-Driven Interpretable Vessel Trajectory Imputation via Large Language Models".

## Abstract
The Automatic Identification System provides critical information for maritime navigation and safety, yet its trajectories are often incomplete due to signal loss or deliberate tampering. Existing imputation methods emphasize trajectory recovery, paying limited attention to interpretability and failing to provide underlying knowledge that benefits downstream tasks such as anomaly detection and route planning. We propose knowledge-driven interpretable vessel trajectory imputation (VISTA), the first trajectory imputation framework that offers interpretability while simultaneously providing underlying knowledge to support downstream analysis. Specifically, we first define underlying knowledge as a combination of Structured Data-derived Knowledge (SDK) distilled from AIS data and Implicit LLM Knowledge acquired from large-scale Internet corpora. Second, to manage and leverage the SDK effectively at scale, we develop a data–knowledge–data loop that employs a Structured Data-derived Knowledge Graph for SDK extraction and knowledge-driven trajectory imputation. Third, to efficiently process large-scale AIS data, we introduce a workflow management layer that coordinates the end-to-end pipeline, enabling parallel knowledge extraction and trajectory imputation with anomaly handling and redundancy elimination. Experiments on two large AIS datasets show that VISTA is capable of state-of-the-art imputation accuracy and computational efficiency, improving over state-of-the-art baselines by 5%–94% and reducing time cost by 51%–93%, while producing interpretable knowledge cues that benefit downstream tasks. 

## Code Structure

```
VISTA/
├── config/
│   └── config.yaml             # Configuration file
├── data/                       # Data directory
│   ├── RawData/                # Original AIS data (unprocessed)
│   ├── CleanedFilteredData/    # Data after cleaning and filtering
│   └── ProcessedData/          # Data after preprocessing and feature extraction
├── results/                    # Experimental results, logs, and evaluation outputs
├── src/                        # Source code
│   ├── data/                   # Data loading, preprocessing, and handling
│   ├── modules/                # Core algorithmic components (e.g., StaticSpatialEncoder, BehaviorAbstraction)
│   ├── pipeline/               # End-to-end Pipelines
│   ├── utils/                  # Utility functions
│   └── main.py                 # Main entry point of the project
│
├── .gitignore
└── Readme.md
```

## Framework Structure

![VISTA Framework](src/Figures/VISTAFramework.svg)

**VISTA** forms a *data–knowledge–data loop* that transforms raw AIS data into structured maritime knowledge and reuses it to reconstruct missing trajectories with interpretable reasoning.
As shown in the figure, the framework is built around four tightly connected components: **AIS Data**, **SD-KG**, **SD-KG Construction**, **Trajectory Imputation**, and a coordinating **Workflow Manager Layer**.

---

### SD-KG and AIS Data

At the center of the framework are **AIS Data** and the **Structured Data-derived Knowledge Graph (SD-KG)** — the two endpoints of the data–knowledge–data loop.
* **AIS Data** (`src/data/AISDataProcessor.py`) provides raw vessel messages and stores reconstructed trajectories under `results/[exp_name]/ImputationResults/`.
  It serves as both the input for knowledge construction and the output repository for imputation results.
* **SD-KG** (`src/modules/M0_SDKG.py`) acts as the central maritime knowledge repository, storing vessel attributes, behavior patterns, and validated imputation methods under `results/[exp_name]/SDKG/`.
  It connects both sides of the loop — continually updated during construction and reused during trajectory imputation.

---

### SD-KG Construction

On the **left side of the framework**, the **SD-KG Construction Workflow Manager** (`SDKG_Construction_Multithreading()` in `src/pipeline/pipeline.py`) orchestrates parallel knowledge extraction from AIS data.
It integrates three key modules corresponding to the blue blocks in the figure:
* **Static & Spatial Encoder** (`generate_vs()` in `M1_StaticSpatialEncoder.py`): extracts vessel attributes and spatial motion cues.
* **Behavior Abstraction** (`generate_vb()` in `M2_BehaviorAbstraction.py`): identifies canonical vessel behavior patterns from time-series trajectories.
* **Method Builder** (`generate_vf()` in `M3_MethodBuilder.py`): generates and validates imputation functions, then inserts them into SD-KG as executable knowledge units.

---

### Trajectory Imputation
On the **right side of the framework**, the **Trajectory Imputation Workflow Manager** (`Trajectory_Imputation_Multithreading()` in `src/pipeline/pipeline.py`) leverages SD-KG to reconstruct missing trajectory segments with interpretable reasoning.
It includes three LLM-driven modules corresponding to the green blocks in the figure:
* **Behavior Estimator** (`behavior_estimator()` in `M4_BehaviorEstimator.py`): infers missing motion patterns using SD-KG priors and vessel context.
* **Method Selector** (`method_selector()` in `M5_MethodSelector.py`): chooses the most suitable imputation function based on graph-supported evidence.
* **Explanation Composer** (`explanation_composer()` in `M6_ExplanationComposer.py`): generates concise, human-readable explanations linking reconstructed trajectories to maritime knowledge and operational logic.
---

### Workflow Manager Layer

The **Workflow Manager Layer** (`src/pipeline/pipeline.py`) bridges construction and imputation, coordinating parallel execution, anomaly handling, and redundancy control through `SDKG_Construction_Multithreading()` and `Trajectory_Imputation_Multithreading()`.


## Setup and Execution

### Environment Setup 
```
bash environment_install.**sh**
```
---
### Dataset Preparation

The datasets **AIS-DK** and **AIS-US** can be automatically downloaded from the following official sources based on the dataset hyperparameter:

* [AIS-DK (Denmark)](http://aisdata.ais.dk/?prefix=2024/)
* [AIS-US (United States)](https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html)

Detailed instructions for downloading, cleaning, and filtering the datasets are provided in
[`./src/data/Readme.md`](./src/data/Readme.md).

After preparing the dataset, update the data path in the configuration file [`./config/config.yaml`](./config/config.yaml). For example:

```yaml
raw_data_file: ./data/CleanedFilteredData/AIS_2024_04_01@15_filtered360_1000000000.csv
```

---

### LLM Setup

VISTA supports the flexibility to choose from various platforms such as [OpenAI](https://platform.openai.com/), [Alibaba Cloud's DashScope](https://modelstudio.console.alibabacloud.com/?spm=a3c0i.29328889.9901980110.3.62eb2d2fshugLx&tab=doc#/doc/?type=model&url=2840914), or others, and configure the corresponding API key for seamless interaction with the selected model.

### Step 1. Select the Platform

Open [`./config/config.yaml`](./config/config.yaml) and update the `base_url:` with your service provider's Base URL (such as `'https://api.openai.com/v1'` for **OpenAI**, or `'https://dashscope.aliyuncs.com/compatible-mode/v1'` for **Alibaba Cloud's DashScope**).

**Example:**
```yaml
base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
```
### Step 2. Obtain and Set the API Key

Open [`./config/config.yaml`](./config/config.yaml) and paste the API key after `llm_api_key:`, which you can obtain from Platforms (e.g., [Alibaba Cloud's DashScope](https://modelstudio.console.alibabacloud.com/?spm=a3c0i.29328889.9901980110.3.62eb2d2fshugLx&tab=doc#/doc/?type=model&url=2840914), [OpenAI](https://platform.openai.com/)). 

**Example:**
```yaml
llm_api_key: sk-xxxxxxxx
```

### Step 3. Choose the Model Types

Open [`./config/config.yaml`](./config/config.yaml) and specify the models you wish to use after `mining_llm:`, `coding_llm:`, and `analysis_llm:`, which you can find on Platfroms (e.g., [Alibaba Cloud's DashScope](https://modelstudio.console.alibabacloud.com/?spm=a3c0i.29328889.9901980110.3.62eb2d2fshugLx&tab=doc#/doc/?type=model&url=2840914), [OpenAI](https://platform.openai.com/docs/models)).

**Example:**
```yaml
mining_llm: gpt-4.1-nano
coding_llm: gpt-3.5-turbo
analysis_llm: qwen-plus
```
---
### Execution

Before running the pipeline, configure key hyperparameters such as `retry_times`, `e_f`, and `top_k` in the [`./config/config.yaml`](./config/config.yaml) file.

Then, execute the following command to start the process:

```
python src/main.py --config config.yaml
```
