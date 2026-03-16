@echo off

cd /d "%~dp0"

:: To start using the system Python, simply run the line below

start pythonw main.py

:: To start using a Conda environment, comment out the line above and
:: uncomment the two lines below, replacing 'env_name' with your env name

:: call conda activate env_name
:: start pythonw main.py

exit