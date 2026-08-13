from pathlib import Path
import runpy

# Build on v1.2.11: fixed global 200-file batches, body search, cumulative results,
# problem-folder skip and bounded parallel parsing.
runpy.run_path('desktop/tools/optimize_content_v131_simple_global_batch.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')

text = text.replace('        super("简搜 PC 1.2.11");\n', '        super("简搜 PC 1.2.12");\n', 1)
text = text.replace(
    '        JLabel description = new JLabel("多线程搜索文件正文：每批固定最多 200 个文件；批次结束释放扫描资源，结果持续累计。");\n',
    '        JLabel description = new JLabel("多线程正文搜索：总文件夹逐个完整处理；同级按名称排序；同一文件本次只搜索一次；每批最多 200 个。");\n',
    1,
)

start_marker = '    private final class SearchWorker extends SwingWorker<Void, ResultItem> {'
end_marker = '    private enum FileCategory {'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('SearchWorker markers not found after v1.2.11 patch')

worker = r'''    private final class SearchWorker extends SwingWorker<Void, ResultItem> {
        private final Path searchRoot;
        private final List<Path> selectedRoots;
        private final List<String> keywords;
        private final boolean caseSensitive;
        private final EnumSet<FileCategory> categories;

        private final AtomicInteger searched = new AtomicInteger();
        private final AtomicInteger matched = new AtomicInteger();
        private final AtomicInteger failed = new AtomicInteger();
        private final AtomicInteger skippedDirectories = new AtomicInteger();
        private final AtomicInteger skippedProblemFolders = new AtomicInteger();
        private final AtomicInteger skippedDuplicateFiles = new AtomicInteger();
        private final AtomicInteger currentBatchCompleted = new AtomicInteger();
        private final AtomicInteger currentBatchTotal = new AtomicInteger();
        private final AtomicInteger activeThreads = new AtomicInteger();
        private final AtomicReference<Path> currentPath = new AtomicReference<>();
        private final AtomicReference<Path> currentTopFolder = new AtomicReference<>();
        private final AtomicReference<Path> lastSkippedFolder = new AtomicReference<>();
        private final AtomicLong lastStatusUpdateNanos = new AtomicLong();
        private final ConcurrentLinkedQueue<ResultItem> pendingResults = new ConcurrentLinkedQueue<>();
        private final Semaphore heavyParserSlots = new Semaphore(HEAVY_PARSER_LIMIT);
        private final Set<String> seenFileKeys = new java.util.HashSet<>();
        private final Set<String> seenFolderKeys = new java.util.HashSet<>();
        private ExecutorService executor;

        private SearchWorker(Path searchRoot, List<Path> selectedRoots, List<String> keywords, boolean caseSensitive, EnumSet<FileCategory> categories) {
            this.searchRoot = searchRoot;
            this.selectedRoots = selectedRoots;
            this.keywords = keywords;
            this.caseSensitive = caseSensitive;
            this.categories = categories;
        }

        @Override
        protected Void doInBackground() throws Exception {
            AtomicInteger threadNumber = new AtomicInteger(1);
            ThreadFactory factory = runnable -> {
                Thread thread = new Thread(runnable, "SimpleSearch-content-" + threadNumber.getAndIncrement());
                thread.setDaemon(true);
                return thread;
            };
            executor = Executors.newFixedThreadPool(SEARCH_THREADS, factory);
            List<Path> batch = new ArrayList<>(FIXED_BATCH_SIZE);

            try {
                // Search direct files under the chosen root first. First-level folders are handled below one-by-one.
                currentTopFolder.set(searchRoot);
                collectDirectFiles(searchRoot, batch);

                List<Path> orderedRoots = new ArrayList<>(selectedRoots);
                orderedRoots.sort(this::comparePathsByName);

                // Important: finish one selected top-level folder and its complete subtree before moving to the next.
                for (Path top : orderedRoots) {
                    checkCancelled();
                    if (isExcludedDirectory(top)) {
                        skippedDirectories.incrementAndGet();
                        continue;
                    }
                    if (isProblemFolder(top)) {
                        markProblemFolder(top);
                        continue;
                    }
                    currentTopFolder.set(top);
                    collectTreeInOrder(top, batch);
                }

                // Only the final global batch may contain fewer than 200 files.
                if (!batch.isEmpty()) {
                    runBatch(batch);
                    batch.clear();
                    releaseAfterBatchIfNeeded();
                }

                drainResults();
                updateStatus(true);
                return null;
            } finally {
                if (executor != null) {
                    executor.shutdownNow();
                    try {
                        executor.awaitTermination(2, TimeUnit.SECONDS);
                    } catch (InterruptedException ignored) {
                        Thread.currentThread().interrupt();
                    }
                }
                drainResults();
            }
        }

        private void collectTreeInOrder(Path top, List<Path> batch) {
            Deque<Path> stack = new ArrayDeque<>();
            stack.addLast(top);

            while (!stack.isEmpty()) {
                checkCancelled();
                Path folder = stack.removeLast();
                String folderKey = canonicalPathKey(folder);
                if (!seenFolderKeys.add(folderKey)) continue;

                if (isExcludedDirectory(folder)) {
                    skippedDirectories.incrementAndGet();
                    continue;
                }
                if (isProblemFolder(folder)) {
                    markProblemFolder(folder);
                    continue;
                }

                List<Path> childFolders = new ArrayList<>();
                collectFolderEntries(folder, childFolders, batch);
                childFolders.sort(this::comparePathsByName);

                // Stack is LIFO, so add in reverse to process ascending name order.
                for (int i = childFolders.size() - 1; i >= 0; i--) {
                    stack.addLast(childFolders.get(i));
                }
            }
        }

        private void collectDirectFiles(Path folder, List<Path> batch) {
            if (isProblemFolder(folder)) {
                markProblemFolder(folder);
                return;
            }
            collectFolderEntries(folder, null, batch);
        }

        private void collectFolderEntries(Path folder, List<Path> childFolders, List<Path> batch) {
            checkCancelled();
            List<Path> files = new ArrayList<>();

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
                    files.add(entry);
                }
            } catch (IOException | SecurityException | DirectoryIteratorException error) {
                markProblemFolder(folder);
            }

            files.sort(this::comparePathsByName);
            for (Path file : files) {
                checkCancelled();
                String key = canonicalPathKey(file);
                if (!seenFileKeys.add(key)) {
                    skippedDuplicateFiles.incrementAndGet();
                    continue;
                }
                batch.add(file);
                if (batch.size() == FIXED_BATCH_SIZE) {
                    runBatch(batch);
                    batch.clear();
                    releaseAfterBatchIfNeeded();
                }
            }
        }

        private int comparePathsByName(Path left, Path right) {
            String a = left == null || left.getFileName() == null ? "" : left.getFileName().toString();
            String b = right == null || right.getFileName() == null ? "" : right.getFileName().toString();
            int byName = a.compareToIgnoreCase(b);
            if (byName != 0) return byName;
            return a.compareTo(b);
        }

        private String canonicalPathKey(Path path) {
            try {
                return path.toRealPath().normalize().toString().toLowerCase(Locale.ROOT);
            } catch (IOException | SecurityException error) {
                return path.toAbsolutePath().normalize().toString().toLowerCase(Locale.ROOT);
            }
        }

        private boolean isExcludedDirectory(Path dir) {
            Path name = dir == null ? null : dir.getFileName();
            if (name == null) return false;
            return EXCLUDED_DIRECTORY_NAMES.contains(name.toString().toLowerCase(Locale.ROOT));
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
        }

        private void runBatch(List<Path> files) {
            checkCancelled();
            int total = files.size();
            currentBatchTotal.set(total);
            currentBatchCompleted.set(0);
            updateStatus(true);

            CountDownLatch latch = new CountDownLatch(total);
            for (Path file : files) {
                executor.execute(() -> {
                    activeThreads.incrementAndGet();
                    try {
                        scanContent(file);
                    } finally {
                        activeThreads.decrementAndGet();
                        currentBatchCompleted.incrementAndGet();
                        latch.countDown();
                    }
                });
            }

            while (latch.getCount() > 0) {
                checkCancelled();
                try {
                    if (latch.await(100, TimeUnit.MILLISECONDS)) break;
                } catch (InterruptedException error) {
                    Thread.currentThread().interrupt();
                    throw new CancellationException();
                }
                drainResults();
                updateStatus(false);
            }

            drainResults();
            updateStatus(true);
        }

        private void scanContent(Path file) {
            if (isCancelled() || Thread.currentThread().isInterrupted()) return;
            currentPath.set(file);
            boolean heavy = isHeavyFormat(file);
            boolean acquired = false;
            try {
                if (heavy) {
                    heavyParserSlots.acquire();
                    acquired = true;
                }
                boolean hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
                searched.incrementAndGet();
                if (hit) {
                    matched.incrementAndGet();
                    // Results remain cumulative across every batch and every top-level folder.
                    pendingResults.add(new ResultItem(file));
                }
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            } catch (CancellationException ignored) {
                // Search cancellation.
            } catch (Exception error) {
                failed.incrementAndGet();
            } finally {
                if (acquired) heavyParserSlots.release();
            }
        }

        private boolean isHeavyFormat(Path file) {
            String name = file.getFileName().toString().toLowerCase(Locale.ROOT);
            return name.endsWith(".pdf") || name.endsWith(".doc") || name.endsWith(".xls");
        }

        private void drainResults() {
            List<ResultItem> chunk = new ArrayList<>(RESULT_BATCH_SIZE);
            ResultItem item;
            while ((item = pendingResults.poll()) != null) {
                chunk.add(item);
                if (chunk.size() >= RESULT_BATCH_SIZE) {
                    publish(chunk.toArray(ResultItem[]::new));
                    chunk.clear();
                }
            }
            if (!chunk.isEmpty()) publish(chunk.toArray(ResultItem[]::new));
        }

        private void releaseAfterBatchIfNeeded() {
            Runtime runtime = Runtime.getRuntime();
            long used = runtime.totalMemory() - runtime.freeMemory();
            long max = runtime.maxMemory();
            if (max > 0 && used * 100L / max >= 75L) System.gc();
        }

        private void updateStatus(boolean force) {
            long now = System.nanoTime();
            long previous = lastStatusUpdateNanos.get();
            if (!force && now - previous < STATUS_UPDATE_INTERVAL_NANOS) return;
            if (!force && !lastStatusUpdateNanos.compareAndSet(previous, now)) return;
            if (force) lastStatusUpdateNanos.set(now);

            int searchedSnapshot = searched.get();
            int matchedSnapshot = matched.get();
            int batchDoneSnapshot = currentBatchCompleted.get();
            int batchTotalSnapshot = currentBatchTotal.get();
            Path pathSnapshot = currentPath.get();
            Path topSnapshot = currentTopFolder.get();
            Path skippedSnapshot = lastSkippedFolder.get();

            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                statusLabel.setText("已搜索 " + searchedSnapshot + " | 当前批 " + batchDoneSnapshot + "/" + batchTotalSnapshot + " | 累计结果 " + matchedSnapshot);
                String detail = "当前总文件夹：" + abbreviatePath(topSnapshot) + "    最近文件：" + abbreviatePath(pathSnapshot);
                if (skippedSnapshot != null) detail += "    最近跳过：" + abbreviatePath(skippedSnapshot);
                currentPathLabel.setText(detail);
                currentPathLabel.setToolTipText(pathSnapshot == null ? "" : pathSnapshot.toString());
            });
        }

        private String abbreviatePath(Path path) {
            if (path == null) return "—";
            String value = path.toString();
            int max = 100;
            return value.length() <= max ? value : "…" + value.substring(value.length() - max + 1);
        }

        private void checkCancelled() {
            if (isCancelled() || Thread.currentThread().isInterrupted()) throw new CancellationException();
        }

        @Override
        protected void process(List<ResultItem> chunks) {
            // Never clear old matches here: results accumulate until this search ends.
            for (ResultItem item : chunks) resultModel.addElement(item);
        }

        @Override
        protected void done() {
            if (executor != null) executor.shutdownNow();
            drainResults();
            startButton.setEnabled(true);
            stopButton.setEnabled(false);
            int searchedCount = searched.get();
            int matchedCount = matched.get();
            int duplicateCount = skippedDuplicateFiles.get();
            int problemCount = skippedProblemFolders.get();
            int failedCount = failed.get();
            if (isCancelled()) {
                statusLabel.setText("正文搜索已停止：已搜索 " + searchedCount + " 个文件，累计结果 " + matchedCount + " 个"
                    + (duplicateCount > 0 ? "，重复文件跳过 " + duplicateCount + " 个" : ""));
            } else {
                try {
                    get();
                    statusLabel.setText("正文搜索完成：已搜索 " + searchedCount + " 个文件，累计结果 " + matchedCount + " 个"
                        + (duplicateCount > 0 ? "，重复文件跳过 " + duplicateCount + " 个" : "")
                        + (problemCount > 0 ? "，问题文件夹跳过 " + problemCount + " 个" : "")
                        + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : ""));
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }
            pendingResults.clear();
            currentPath.set(null);
            currentTopFolder.set(null);
            executor = null;
            currentWorker = null;
        }
    }

'''

text = text[:start] + worker + text[end:]

pom = pom.replace('<version>1.2.11</version>\n    <name>简搜 PC</name>', '<version>1.2.12</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.11</finalName>', '<finalName>simpletxtsearch-pc-1.2.12</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.12 ordered top-folder traversal + canonical file dedup')
