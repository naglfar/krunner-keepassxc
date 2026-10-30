from importlib.metadata import PackageNotFoundError, version

# the version is maintained in pyproject.toml only (scripts/set_version.py updates the other files)
try:
	__version__ = version('krunner-keepassxc')
except PackageNotFoundError:
	# running from the source tree without installing the package
	__version__ = '0+unknown'
