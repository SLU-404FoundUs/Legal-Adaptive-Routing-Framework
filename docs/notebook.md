# Jupyter Notebook Setup Guide

This guide explains how to set up your development environment to run Jupyter Notebooks in this project using a dedicated virtual environment.

## 1. Environment Setup

It is recommended to use a virtual environment to manage dependencies.

### Create and Activate Virtual Environment
```bash
# Create a virtual environment named 'myvenv'
python -m venv myvenv

# Activate it (macOS/Linux)
source myvenv/bin/activate

# Activate it (Windows)
# .\myvenv\Scripts\activate
```

### Install Project Dependencies
```bash
pip install -r requirements.txt
```

## 2. Configure Jupyter Kernel

To make your virtual environment available inside Jupyter Notebooks, you need to install and register `ipykernel`.

### Install ipykernel
```bash
pip install ipykernel
```

### Register the Kernel
Run the following command to register the environment as a selectable kernel in Jupyter:
```bash
python -m ipykernel install --user --name=myvenv --display-name "Python (myvenv)"
```

## 3. Selecting the Kernel

Once the setup is complete, you can select the kernel in your preferred editor.

### In VS Code:
1. Open any `.ipynb` file (e.g., `notebook/triage-eval.ipynb`).
2. Click on the **Kernel selection** button in the top-right corner of the editor.
3. Select **Python (myvenv)** from the list.

### In Jupyter Lab / Notebook:
1. Start Jupyter: `jupyter lab` or `jupyter notebook`.
2. Open your notebook.
3. Go to **Kernel** -> **Change Kernel** -> **Python (myvenv)**.

## 4. Maintenance

If you install new packages in your virtual environment:
```bash
pip install <package-name>
```
They will be available to the notebook immediately as long as the "Python (myvenv)" kernel is selected.
