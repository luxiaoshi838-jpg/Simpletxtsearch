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
    '        JLabel description = new JLabel("多线程正文搜索：唯一文件先登记，再进入固定200批次；同一文件本次只提交一次，结果持续累计。");\n'
)

# Explicit accounting: registered unique files -> submitted tasks -> completed body searches.
replace_once(
    '        private final AtomicInteger searched = new AtomicInteger();\n',
    '        private final AtomicInteger registeredUniqueFiles = new AtomicInteger();\n'
    '        private final AtomicInteger submittedTasks = new AtomicInteger();\n'
    '        private final AtomicInteger searched = new AtomicInteger();\n'
)

# Use physical filesystem identity for folders/files where available.
replace_once(
    '''                String folderKey = canonicalPathKey(folder);\n                if (!seenFolderKeys.add(folderKey)) continue;\n''',
    '''                String folderKey = physicalIdentityKey(folder, true);\n                if (!seenFolderKeys.add(folderKey)) continue;\n'''
)

replace_once(
    '''                String key = canonicalPathKey(file);\n                if (!seenFileKeys.add(key)) {\n                    skippedDuplicateFiles.incrementAndGet();\n                    continue;\n                }\n                batch.add(file);\n''',
    '''                String key = physicalIdentityKey(file, false);\n                if (!seenFileKeys.add(key)) {\n                    skippedDuplicateFiles.incrementAndGet();\n                    continue;\n                }\n                registeredUniqueFiles.incrementAndGet();\n                batch.add(file);\n'''
)

old_key = '''        private String canonicalPathKey(Path path) {\n            try {\n                return path.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException error) {\n                return path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);\n            }\n        }\n'''
new_key = '''        private String physicalIdentityKey(Path path, boolean directory) {\n            String prefix = directory ? "D:" : "F:";\n            try {\n                BasicFileAttributes attrs = Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);\n                Object fileKey = attrs.fileKey();\n                if (fileKey != null) return prefix + "KEY:" + fileKey.toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException ignored) {\n                // Fall back to real/absolute path below.\n            }\n            try {\n                return prefix + "PATH:" + path.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);\n            } catch (IOException | SecurityException error) {\n                return prefix + "ABS:" + path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);\n            }\n        }\n'''
replace_once(old_key, new_key)

# Harden batch submission. A task cannot exist unless that unique file was registered first.
replace_once(
    '''            CountDownLatch latch = new CountDownLatch(total);\n            for (Path file : files) {\n                executor.execute(() -> {\n''',
    '''            int registeredNow = registeredUniqueFiles.get();\n            int alreadySubmitted = submittedTasks.get();\n            if (alreadySubmitted + total > registeredNow) {\n                throw new IllegalStateException("任务计数异常：提交任务数不能超过唯一文件数");\n            }\n\n            CountDownLatch latch = new CountDownLatch(total);\n            for (Path file : files) {\n                submittedTasks.incrementAndGet();\n                executor.execute(() -> {\n'''
)

# Status shows independently auditable counts.
replace_once(
    '''            int searchedSnapshot = searched.get();\n            int matchedSnapshot = matched.get();\n''',
    '''            int uniqueSnapshot = registeredUniqueFiles.get();\n            int submittedSnapshot = submittedTasks.get();\n            int searchedSnapshot = searched.get();\n            int matchedSnapshot = matched.get();\n'''
)
replace_once(
    '''                statusLabel.setText("已搜索 " + searchedSnapshot + " | 当前批 " + batchDoneSnapshot + "/" + batchTotalSnapshot + " | 累计结果 " + matchedSnapshot);\n''',
    '''                statusLabel.setText("唯一文件 " + uniqueSnapshot + " | 已提交 " + submittedSnapshot + " | 已搜索 " + searchedSnapshot\n                    + " | 当前批 " + batchDoneSnapshot + "/" + batchTotalSnapshot + " | 累计结果 " + matchedSnapshot);\n'''
)

# Completion summary also exposes the three counters.
replace_once(
    '''            int searchedCount = searched.get();\n            int matchedCount = matched.get();\n''',
    '''            int uniqueCount = registeredUniqueFiles.get();\n            int submittedCount = submittedTasks.get();\n            int searchedCount = searched.get();\n            int matchedCount = matched.get();\n'''
)
replace_once(
    '''                statusLabel.setText("正文搜索已停止：已搜索 " + searchedCount + " 个文件，累计结果 " + matchedCount + " 个"\n''',
    '''                statusLabel.setText("正文搜索已停止：唯一文件 " + uniqueCount + "，已提交 " + submittedCount + "，已搜索 " + searchedCount\n                    + "，累计结果 " + matchedCount + " 个"\n'''
)
replace_once(
    '''                    statusLabel.setText("正文搜索完成：已搜索 " + searchedCount + " 个文件，累计结果 " + matchedCount + " 个"\n''',
    '''                    statusLabel.setText("正文搜索完成：唯一文件 " + uniqueCount + "，已提交 " + submittedCount + "，已搜索 " + searchedCount\n                        + "，累计结果 " + matchedCount + " 个"\n'''
)

pom = pom.replace('<version>1.2.12</version>\n    <name>简搜 PC</name>', '<version>1.2.13</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.12</finalName>', '<finalName>simpletxtsearch-pc-1.2.13</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.13 physical file dedup + hard unique-task accounting')
