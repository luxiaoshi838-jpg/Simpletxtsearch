from pathlib import Path
import runpy

# Build on v1.2.12 ordered traversal + global fixed-200 batching.
runpy.run_path('desktop/tools/optimize_content_v132_ordered_dedup.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected v1.2.12 fragment not found: {old[:260]!r}')
    text = text.replace(old, new, 1)

replace_once('        super("简搜 PC 1.2.12");\n', '        super("简搜 PC 1.2.13");\n')
replace_once(
    '        JLabel description = new JLabel("多线程正文搜索：总文件夹逐个完整处理；同级按名称排序；同一文件本次只搜索一次；每批最多 200 个。");\n',
    '        JLabel description = new JLabel("多线程正文搜索：总文件夹逐个处理；按物理文件身份去重；重解析目录跳过；每批最多 200 个。");\n'
)

# Directory traversal: identify actual filesystem objects, not just path strings.
replace_once(
    '''                String folderKey = canonicalPathKey(folder);\n                if (!seenFolderKeys.add(folderKey)) continue;\n''',
    '''                String folderKey = physicalIdentityKey(folder, true);\n                if (!seenFolderKeys.add(folderKey)) continue;\n'''
)

# Replace metadata classification so Windows junction/reparse-like entries are never followed.
replace_once(
    '''                    try {\n                        if (Files.isSymbolicLink(entry)) {\n                            if (Files.isDirectory(entry)) markProblemFolder(entry);\n                            continue;\n                        }\n                        if (Files.isDirectory(entry, LinkOption.NOFOLLOW_LINKS)) {\n                            if (childFolders != null) childFolders.add(entry);\n                            continue;\n                        }\n                        if (!Files.isRegularFile(entry, LinkOption.NOFOLLOW_LINKS)) continue;\n                    } catch (SecurityException error) {\n                        continue;\n                    }\n''',
    '''                    try {\n                        BasicFileAttributes attrs = Files.readAttributes(entry, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);\n                        // On Windows, directory junctions/reparse points can otherwise expand the same tree repeatedly.\n                        // Do not follow symbolic/other reparse-like filesystem entries.\n                        if (attrs.isSymbolicLink() || attrs.isOther()) {\n                            if (!attrs.isRegularFile()) markProblemFolder(entry);\n                            continue;\n                        }\n                        if (attrs.isDirectory()) {\n                            if (childFolders != null) childFolders.add(entry);\n                            continue;\n                        }\n                        if (!attrs.isRegularFile()) continue;\n                    } catch (IOException | SecurityException error) {\n                        continue;\n                    }\n'''
)

replace_once(
    '''                String key = canonicalPathKey(file);\n                if (!seenFileKeys.add(key)) {\n''',
    '''                String key = physicalIdentityKey(file, false);\n                if (!seenFileKeys.add(key)) {\n'''
)

# Replace path-only key with filesystem fileKey first. fileKey identifies the same physical file even via hard links.
old_key = '''        private String canonicalPathKey(Path path) {\n            try {\n                return path.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException error) {\n                return path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);\n            }\n        }\n'''
new_key = '''        private String physicalIdentityKey(Path path, boolean directory) {\n            String prefix = directory ? "D:" : "F:";\n            try {\n                BasicFileAttributes attrs = Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);\n                Object fileKey = attrs.fileKey();\n                if (fileKey != null) return prefix + "KEY:" + fileKey.toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException ignored) {\n                // Fall back to canonical path below.\n            }\n            try {\n                return prefix + "PATH:" + path.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException error) {\n                return prefix + "ABS:" + path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);\n            }\n        }\n'''
replace_once(old_key, new_key)

# Strengthen problem-folder detection: any no-follow non-directory object (including junction/reparse-like entries) is skipped.
old_problem = '''        private boolean isProblemFolder(Path dir) {\n            try {\n                if (dir == null) return true;\n                if (Files.isSymbolicLink(dir)) return true;\n                if (!Files.isDirectory(dir, LinkOption.NOFOLLOW_LINKS)) return true;\n                return !Files.isReadable(dir);\n            } catch (SecurityException error) {\n                return true;\n            }\n        }\n'''
new_problem = '''        private boolean isProblemFolder(Path dir) {\n            try {\n                if (dir == null) return true;\n                BasicFileAttributes attrs = Files.readAttributes(dir, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);\n                if (attrs.isSymbolicLink() || attrs.isOther()) return true;\n                if (!attrs.isDirectory()) return true;\n                return !Files.isReadable(dir);\n            } catch (IOException | SecurityException error) {\n                return true;\n            }\n        }\n'''
replace_once(old_problem, new_problem)

pom = pom.replace('<version>1.2.12</version>\n    <name>简搜 PC</name>', '<version>1.2.13</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.12</finalName>', '<finalName>simpletxtsearch-pc-1.2.13</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.13 physical file identity dedup + Windows reparse/junction skip')
