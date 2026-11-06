import os
import configparser
from pathlib import Path


config = configparser.ConfigParser()

def get_base_config_dir() -> Path:
	BASE_DIR = Path(__file__).resolve().parent.parent.parent
	if not BASE_DIR.exists():
		raise FileNotFoundError(f"config directory not found at {BASE_DIR}")
	return BASE_DIR

def get_base_config_file(file_name: str = "config.conf") -> Path:
	BASE_DIR = Path(__file__).resolve().parent.parent.parent
	if not BASE_DIR.exists():
		raise FileNotFoundError(f"config file not found at {BASE_DIR}")
	return BASE_DIR / file_name

config_file_path = get_base_config_file()
config.read(config_file_path, encoding="utf-8")
