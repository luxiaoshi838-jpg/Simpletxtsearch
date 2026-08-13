from pathlib import Path
import runpy

# Build on v1.2.9: folder-batch multithreaded body search + problem-folder auto skip.
runpy.run_path('desktop/tools/optimize_content_v129_problem_folder_skip.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected v1.2.9 fragment not found: {old[:220]!r}')
    text = text.replace(old, new, 1)

# Version + description.
replace_once('        super("简搜 PC 1.2.9");\n', '        super("简搜 PC 1.2.10");\n')
replace_once(
    '        JLabel description = new JLabel("多线程搜索文件正文：按文件夹分批处理；异常/无权限/链接类问题文件夹自动跳过，结果继续累计。");\n',
    '        JLabel description = new JLabel("多线程搜索文件正文：显示数量只统计实际完成正文搜索的文件；重复/异常目录自动跳过。");\n'
)

# Add canonical-folder de-duplication support.
replace_once('import java.util.EnumSet;\n', 'import java.util.EnumSet;\nimport java.util.HashSet;\n')
replace_once(
    '        private final AtomicInteger skippedProblemFolders = new AtomicInteger();\n',
    '        private final AtomicInteger skippedProblemFolders = new AtomicInteger();\n'
    '        private final AtomicInteger skippedDuplicateFolders = new AtomicInteger();\n'
)
replace_once(
    '        private final ConcurrentLinkedQueue<ResultItem> pendingResults = new ConcurrentLinkedQueue<>();\n',
    '        private final ConcurrentLinkedQueue<ResultItem> pendingResults = new ConcurrentLinkedQueue<>();\n'
    '        private final Set<String> seenFolderKeys = new HashSet<>();\n'
)

# Root is processed once; selected/sub folders enter through a de-duplicating enqueue method.
replace_once(
    '''                Deque<Path> folderQueue = new ArrayDeque<>();
                for (Path selected : selectedRoots) {
                    if (isExcludedDirectory(selected)) {
                        skippedDirectories.incrementAndGet();
                    } else if (isProblemFolder(selected)) {
                        markProblemFolder(selected);
                    } else {
                        folderQueue.addLast(selected);
                    }
                }
''',
    '''                Deque<Path> folderQueue = new ArrayDeque<>();
                seenFolderKeys.add(folderKey(searchRoot));
                for (Path selected : selectedRoots) enqueueFolder(folderQueue, selected);
'''
)

replace_once(
    '''                                if (isExcludedDirectory(entry)) {
                                    skippedDirectories.incrementAndGet();
                                } else if (isProblemFolder(entry)) {
                                    markProblemFolder(entry);
                                } else {
                                    folderQueue.addLast(entry);
                                }
''',
    '''                                enqueueFolder(folderQueue, entry);
'''
)

# Inject robust folder identity. toRealPath follows Windows junctions/reparse targets where accessible,
# so the same physical directory cannot be queued repeatedly through different visible paths.
anchor = '''        private boolean isProblemFolder(Path dir) {
'''
insert = '''        private void enqueueFolder(Deque<Path> folderQueue, Path dir) {
            if (dir == null) return;
            if (isExcludedDirectory(dir)) {
                skippedDirectories.incrementAndGet();
                return;
            }
            if (isProblemFolder(dir)) {
                markProblemFolder(dir);
                return;
            }
            String key = folderKey(dir);
            if (!seenFolderKeys.add(key)) {
                skippedDuplicateFolders.incrementAndGet();
                return;
            }
            folderQueue.addLast(dir);
        }

        private String folderKey(Path dir) {
            try {
                return dir.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);
            } catch (IOException | SecurityException error) {
                return dir.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);
            }
        }

'''
if anchor not in text:
    raise SystemExit('Could not locate isProblemFolder anchor')
text = text.replace(anchor, insert + anchor, 1)

# Count a file as searched ONLY after ContentSearch returned normally.
replace_once(
    '''                scanned.incrementAndGet();
                boolean hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
                if (hit) {
''',
    '''                boolean hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
                scanned.incrementAndGet();
                if (hit) {
'''
)

# Live status: stop presenting every discovered regular file as a searched-file count.
replace_once(
    '            int visitedSnapshot = visited.get();\n',
    '            int visitedSnapshot = visited.get();\n'
    '            int duplicateFolderSnapshot = skippedDuplicateFolders.get();\n'
)
replace_once(
    '''                statusLabel.setText("正文搜索 " + SEARCH_THREADS + "线程：遍历 " + visitedSnapshot
                    + " 个，读取正文 " + scannedSnapshot + " 个，累计结果 " + matchedSnapshot
''',
    '''                statusLabel.setText("正文搜索 " + SEARCH_THREADS + "线程：已完成正文搜索 " + scannedSnapshot
                    + " 个文件，累计结果 " + matchedSnapshot
'''
)
replace_once(
    '''                    + (directorySnapshot > 0 ? "，排除目录 " + directorySnapshot + " 个" : "")
                    + (problemFolderSnapshot > 0 ? "，问题文件夹自动跳过 " + problemFolderSnapshot + " 个" : "")
''',
    '''                    + (directorySnapshot > 0 ? "，排除目录 " + directorySnapshot + " 个" : "")
                    + (problemFolderSnapshot > 0 ? "，问题文件夹自动跳过 " + problemFolderSnapshot + " 个" : "")
                    + (duplicateFolderSnapshot > 0 ? "，重复目录跳过 " + duplicateFolderSnapshot + " 个" : "")
'''
)

# Completion summary uses only successfully completed body-search count as the headline count.
replace_once(
    '            int visitedCount = visited.get();\n',
    '            int visitedCount = visited.get();\n'
    '            int duplicateFolderCount = skippedDuplicateFolders.get();\n'
)
replace_once(
    '''                statusLabel.setText("正文搜索已停止：遍历 " + visitedCount + " 个文件，读取正文 " + scannedCount
                    + " 个，累计结果 " + matchedCount + " 个；已完成 " + completedBatches.get() + " 批");
''',
    '''                statusLabel.setText("正文搜索已停止：已完成正文搜索 " + scannedCount
                    + " 个文件，累计结果 " + matchedCount + " 个；已完成 " + completedBatches.get() + " 批"
                    + (duplicateFolderCount > 0 ? "，重复目录跳过 " + duplicateFolderCount + " 个" : ""));
'''
)
replace_once(
    '''                    statusLabel.setText("正文搜索完成：" + SEARCH_THREADS + "线程，遍历 " + visitedCount + " 个文件，读取正文 "
                        + scannedCount + " 个，累计结果 " + matchedCount + " 个；完成 " + completedBatches.get() + " 批"
''',
    '''                    statusLabel.setText("正文搜索完成：" + SEARCH_THREADS + "线程，实际完成正文搜索 "
                        + scannedCount + " 个文件，累计结果 " + matchedCount + " 个；完成 " + completedBatches.get() + " 批"
'''
)
replace_once(
    '''                        + (problemFolderCount > 0 ? "，问题文件夹自动跳过 " + problemFolderCount + " 个" : "")
                        + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : ""));
''',
    '''                        + (problemFolderCount > 0 ? "，问题文件夹自动跳过 " + problemFolderCount + " 个" : "")
                        + (duplicateFolderCount > 0 ? "，重复目录跳过 " + duplicateFolderCount + " 个" : "")
                        + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : ""));
'''
)

pom = pom.replace('<version>1.2.9</version>\n    <name>简搜 PC</name>', '<version>1.2.10</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.9</finalName>', '<finalName>simpletxtsearch-pc-1.2.10</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.10 searched-count correction + canonical folder de-duplication')
