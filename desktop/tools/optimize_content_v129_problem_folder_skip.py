from pathlib import Path
import runpy

# Build on the verified v1.2.8 folder-batch + multithreaded content-search baseline.
runpy.run_path('desktop/tools/optimize_content_v128_folder_batches_driver.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected v1.2.8 fragment not found: {old[:220]!r}')
    text = text.replace(old, new, 1)


# Runtime directory fault handling imports.
replace_once('import java.nio.file.Files;\n', 'import java.nio.file.DirectoryIteratorException;\nimport java.nio.file.Files;\nimport java.nio.file.LinkOption;\n')

replace_once('        super("简搜 PC 1.2.8");\n', '        super("简搜 PC 1.2.9");\n')
replace_once(
    '        JLabel description = new JLabel("多线程搜索文件正文：按文件夹分批处理；每批结束即释放扫描资源。结果持续累计，双击结果直接打开原文件。");\n',
    '        JLabel description = new JLabel("多线程搜索文件正文：按文件夹分批处理；异常/无权限/链接类问题文件夹自动跳过，结果继续累计。");\n'
)

# Track problem folders separately from normal configured exclusions.
replace_once(
    '        private final AtomicInteger skippedDirectories = new AtomicInteger();\n',
    '        private final AtomicInteger skippedDirectories = new AtomicInteger();\n'
    '        private final AtomicInteger skippedProblemFolders = new AtomicInteger();\n'
)
replace_once(
    '        private final AtomicReference<Path> currentPath = new AtomicReference<>();\n',
    '        private final AtomicReference<Path> currentPath = new AtomicReference<>();\n'
    '        private final AtomicReference<Path> lastSkippedFolder = new AtomicReference<>();\n'
)

replace_once(
    '''                for (Path selected : selectedRoots) {\n                    if (isExcludedDirectory(selected)) skippedDirectories.incrementAndGet();\n                    else folderQueue.addLast(selected);\n                }\n''',
    '''                for (Path selected : selectedRoots) {\n                    if (isExcludedDirectory(selected)) {\n                        skippedDirectories.incrementAndGet();\n                    } else if (isProblemFolder(selected)) {\n                        markProblemFolder(selected);\n                    } else {\n                        folderQueue.addLast(selected);\n                    }\n                }\n'''
)

old_process = r'''        private void processFolder(Path folder, boolean collectChildren, Deque<Path> folderQueue) {
            checkCancelled();
            currentFolder.set(folder);
            List<Path> batch = new ArrayList<>(batchSize);

            try (var stream = Files.newDirectoryStream(folder)) {
                for (Path entry : stream) {
                    checkCancelled();
                    if (Files.isDirectory(entry)) {
                        if (collectChildren && folderQueue != null) {
                            if (isExcludedDirectory(entry)) skippedDirectories.incrementAndGet();
                            else folderQueue.addLast(entry);
                        }
                        continue;
                    }
                    if (!Files.isRegularFile(entry)) continue;
                    visited.incrementAndGet();
                    FileCategory category = FileCategory.from(entry);
                    if (category == null || !categories.contains(category)) continue;

                    batch.add(entry);
                    if (batch.size() >= batchSize) {
                        runBatch(batch);
                        batch.clear();
                        releaseAfterBatchIfNeeded();
                    }
                }
            } catch (IOException error) {
                failed.incrementAndGet();
            }

            if (!batch.isEmpty()) {
                runBatch(batch);
                batch.clear();
                releaseAfterBatchIfNeeded();
            }
        }
'''

new_process = r'''        private void processFolder(Path folder, boolean collectChildren, Deque<Path> folderQueue) {
            checkCancelled();
            currentFolder.set(folder);

            // A bad directory must never abort the whole search. Validate without following links/junction-like entries.
            if (isProblemFolder(folder)) {
                markProblemFolder(folder);
                return;
            }

            List<Path> batch = new ArrayList<>(batchSize);
            boolean folderEnumerationFailed = false;

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
                        folderEnumerationFailed = true;
                        break;
                    }

                    try {
                        if (Files.isSymbolicLink(entry)) {
                            if (Files.isDirectory(entry)) markProblemFolder(entry);
                            continue;
                        }

                        if (Files.isDirectory(entry, LinkOption.NOFOLLOW_LINKS)) {
                            if (collectChildren && folderQueue != null) {
                                if (isExcludedDirectory(entry)) {
                                    skippedDirectories.incrementAndGet();
                                } else if (isProblemFolder(entry)) {
                                    markProblemFolder(entry);
                                } else {
                                    folderQueue.addLast(entry);
                                }
                            }
                            continue;
                        }

                        if (!Files.isRegularFile(entry, LinkOption.NOFOLLOW_LINKS)) continue;
                    } catch (SecurityException error) {
                        // Entry metadata itself is inaccessible. Skip the entry and keep this folder moving.
                        continue;
                    }

                    visited.incrementAndGet();
                    FileCategory category = FileCategory.from(entry);
                    if (category == null || !categories.contains(category)) continue;

                    batch.add(entry);
                    if (batch.size() >= batchSize) {
                        runBatch(batch);
                        batch.clear();
                        releaseAfterBatchIfNeeded();
                    }
                }
            } catch (IOException | SecurityException | DirectoryIteratorException error) {
                markProblemFolder(folder);
                folderEnumerationFailed = true;
            }

            // Files already collected before an enumeration failure are still valid work; finish them once, then move on.
            if (!batch.isEmpty()) {
                runBatch(batch);
                batch.clear();
                releaseAfterBatchIfNeeded();
            }

            if (folderEnumerationFailed) updateStatus(true, 0);
        }

        private boolean isProblemFolder(Path dir) {
            try {
                if (dir == null) return true;
                if (Files.isSymbolicLink(dir)) return true;
                if (!Files.isDirectory(dir, LinkOption.NOFOLLOW_LINKS)) return true;
                return !Files.isReadable(dir);
            } catch (SecurityException error) {
                return true;
            }
        }

        private void markProblemFolder(Path dir) {
            skippedProblemFolders.incrementAndGet();
            lastSkippedFolder.set(dir);
            currentFolder.set(dir);
        }
'''
replace_once(old_process, new_process)

# Show problem-directory state live, including the last path skipped.
replace_once(
    '            int directorySnapshot = skippedDirectories.get();\n',
    '            int directorySnapshot = skippedDirectories.get();\n'
    '            int problemFolderSnapshot = skippedProblemFolders.get();\n'
)
replace_once(
    '            Path pathSnapshot = currentPath.get();\n',
    '            Path pathSnapshot = currentPath.get();\n'
    '            Path skippedFolderSnapshot = lastSkippedFolder.get();\n'
)
replace_once(
    '''                    + (directorySnapshot > 0 ? "，排除目录 " + directorySnapshot + " 个" : "")\n                    + (failedSnapshot > 0 ? "，读取失败 " + failedSnapshot + " 个" : ""));\n                currentPathLabel.setText("文件夹：" + abbreviatePath(folderSnapshot) + "    最近文件：" + abbreviatePath(pathSnapshot));\n''',
    '''                    + (directorySnapshot > 0 ? "，排除目录 " + directorySnapshot + " 个" : "")\n                    + (problemFolderSnapshot > 0 ? "，问题文件夹自动跳过 " + problemFolderSnapshot + " 个" : "")\n                    + (failedSnapshot > 0 ? "，读取失败 " + failedSnapshot + " 个" : ""));\n                currentPathLabel.setText("文件夹：" + abbreviatePath(folderSnapshot) + "    最近文件：" + abbreviatePath(pathSnapshot)\n                    + (problemFolderSnapshot > 0 ? "    最近跳过：" + abbreviatePath(skippedFolderSnapshot) : ""));\n'''
)

# Completion summary includes problem-folder skips.
replace_once(
    '            int directoryCount = skippedDirectories.get();\n',
    '            int directoryCount = skippedDirectories.get();\n'
    '            int problemFolderCount = skippedProblemFolders.get();\n'
)
replace_once(
    '''                statusLabel.setText("正文搜索已停止：遍历 " + visitedCount + " 个文件，读取正文 " + scannedCount\n                    + " 个，累计结果 " + matchedCount + " 个；已完成 " + completedBatches.get() + " 批");\n''',
    '''                statusLabel.setText("正文搜索已停止：遍历 " + visitedCount + " 个文件，读取正文 " + scannedCount\n                    + " 个，累计结果 " + matchedCount + " 个；已完成 " + completedBatches.get() + " 批"\n                    + (problemFolderCount > 0 ? "，问题文件夹自动跳过 " + problemFolderCount + " 个" : ""));\n'''
)
replace_once(
    '''                        + (directoryCount > 0 ? "，排除目录 " + directoryCount + " 个" : "")\n                        + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : ""));\n''',
    '''                        + (directoryCount > 0 ? "，排除目录 " + directoryCount + " 个" : "")\n                        + (problemFolderCount > 0 ? "，问题文件夹自动跳过 " + problemFolderCount + " 个" : "")\n                        + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : ""));\n'''
)

# Update version metadata generated by v1.2.8.
pom = pom.replace('<version>1.2.8</version>\n    <name>简搜 PC</name>', '<version>1.2.9</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.8</finalName>', '<finalName>simpletxtsearch-pc-1.2.9</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.9 problem-folder auto-skip tolerance')
