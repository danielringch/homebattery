import sys
import os

project = 'homebattery'
author = 'Daniel Ring'
copyright = u'2024, Daniel Ring'
version = '0.3'
release = '0.3.0'

extensions = [
    'sphinx_rtd_theme',
]

html_theme_options = {
    'navigation_depth': 3,
}

source_suffix = '.rst'
source_encoding = 'utf-8-sig'

root_doc = 'index'
exclude_patterns = []

language = 'en'

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
