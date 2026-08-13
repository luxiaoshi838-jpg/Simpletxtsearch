from pathlib import Path
import runpy

# Build on v1.2.13: ordered top-folder traversal, fixed 200-file batches,
# cumulative results, unique/submitted/searched accounting, and problem-folder skip.
runpy.run_path('desktop/tools/optimize_content_v133_physical_identity_dedup.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected v1.2.13 fragment not found: {old[:260]!r}')
    text = text.replace(old, new, 1)


replace_once('        super("简搜 PC 1.2.13");\n', '        super("简搜 PC 1.2.14");\n')
replace_once(
    '        JLabel description = new JLabel("多线程正文搜索：唯一文件先登记，再进入固定200批次；同一文件本次只提交一次，结果持续累计。");\n',
    '        JLabel description = new JLabel("多线程正文搜索：轻量路径去重，发现文件即加入固定200批次；同一文件本次只提交一次，结果持续累计。");\n'
)

# v1.2.13 read filesystem attributes/fileKey for every file. That is robust but expensive on
# large HDD/network folders. Use normalized absolute path as the normal-file identity instead.
# Symbolic links are already skipped by traversal, so the common case needs no extra I/O.
old_key = '''        private String physicalIdentityKey(Path path, boolean directory) {\n            String prefix = directory ? "D:" : "F:";\n            try {\n                BasicFileAttributes attrs = Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);\n                Object fileKey = attrs.fileKey();\n                if (fileKey != null) return prefix + "KEY:" + fileKey.toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException ignored) {\n                // Fall back to real/absolute path below.\n            }\n            try {\n                return prefix + "PATH:" + path.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException error) {\n                return prefix + "ABS:" + path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);\n            }\n        }\n'''
new_key = '''        private String physicalIdentityKey(Path path, boolean directory) {\n            String prefix = directory ? "D:" : "F:";\n            return prefix + path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);\n        }\n'''
replace_once(old_key, new_key)

# Stream ordinary files directly into the global 200-file batch. Do not first collect every file
# in the folder and sort it; only child folders need sorting to preserve deterministic folder order.
method_start = text.find('        private void collectFolderEntries(Path folder, List<Path> childFolders, List<Path> batch) {')
method_end = text.find('        private int comparePathsByName(Path left, Path right) {', method_start)
if method_start < 0 or method_end < 0:
    raise SystemExit('collectFolderEntries markers not found after v1.2.13 patch')

new_method = r'''        private void collectFolderEntries(Path folder, List<Path> childFolders, List<Path> batch) {
            checkCancelled();

            try (var stream = Files.newDirectoryStream(folder)) {
                var iterator = stream.iterator();
                while (true) {
                    checkCancelled();
                    Path entry;
                    try {
                        if (!iterator.hasNext()) break;
                        entry = iterator.next();
                    } catch (DirectoryIteratorException | SecurityException error) {
                        markProblemFolder(folder);
                        break;
                    }

                    try {
                        if (Files.isSymbolicLink(entry)) {
                            if (Files.isDirectory(entry)) markProblemFolder(entry);
                            continue;
                        }
                        if (Files.isDirectory(entry, LinkOption.NOFOLLOW_LINKS)) {
                            if (childFolders != null) childFolders.add(entry);
                            continue;
                        }
                        if (!Files.isRegularFile(entry, LinkOption.NOFOLLOW_LINKS)) continue;
                    } catch (SecurityException error) {
                        continue;
                    }

                    FileCategory category = FileCategory.from(entry);
                    if (category == null || !categories.contains(category)) continue;

                    // Fast, allocation-light normal-file dedup: no fileKey/toRealPath I/O.
                    String key = physicalIdentityKey(entry, false);
                    if (!seenFileKeys.add(key)) {
                        skippedDuplicateFiles.incrementAndGet();
                        continue;
                    }
                    registeredUniqueFiles.incrementAndGet();
                    batch.add(entry);

                    // Start body search as soon as 200 unique files are available.
                    if (batch.size() == FIXED_BATCH_SIZE) {
                        runBatch(batch);
                        batch.clear();
                        releaseAfterBatchIfNeeded();
                    }
                }
            } catch (IOException | SecurityException | DirectoryIteratorException error) {
                markProblemFolder(folder);
            }
        }

'''
text = text[:method_start] + new_method + text[method_end:]

pom = pom.replace('<version>1.2.13</version>\n    <name>简搜 PC</name>', '<version>1.2.14</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.13</finalName>', '<finalName>simpletxtsearch-pc-1.2.14</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.14 fast path dedup + streaming batch fill')
