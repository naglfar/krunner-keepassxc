import configparser

# configparser patched to handle comments
class CommentConfigParser(configparser.ConfigParser):
	def write(self, fp, space_around_delimiters=True):
		if self._defaults:
			self._write_section_dict(fp, self.default_section, self._defaults.items(), space_around_delimiters)

		for section in self._sections:
			self._write_section_dict(fp, section, self._sections[section].items(), space_around_delimiters)

	def _write_section_dict(self, fp, section_name, items, space_around_delimiters):
		fp.write(f"[{section_name}]\n")
		for key, value in items:
			if key.startswith("comment_line_"):
				fp.write(f"{value}\n")
			else:
				if space_around_delimiters:
					fp.write(f"{key} = {value}\n")
				else:
					fp.write(f"{key}={value}\n")
		fp.write("\n")

	def _read(self, fp, fpname):
		comment_count = 0

		lines = fp if isinstance(fp, list) else list(fp)
		cleaned_lines = []

		for line in lines:
			stripped = line.strip()

			if stripped.startswith('[') and stripped.endswith(']'):
				cleaned_lines.append(line)
				continue

			if stripped.startswith('#') or stripped.startswith(';'):
				comment_key = f"comment_line_{comment_count}"
				comment_count += 1
				cleaned_lines.append(f"{comment_key} = {stripped}\n")
			else:
				cleaned_lines.append(line)

		super()._read(cleaned_lines, fpname)