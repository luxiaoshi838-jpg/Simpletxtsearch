from pathlib import Path

src = Path('desktop/tools/optimize_content_v127_folder_batches.py').read_text(encoding='utf-8')

wrong = '''        savePreferences(categories);\\n        resultModel.clear();\\n        currentPathLabel.setText(\"当前：准备扫描……\");\\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories);\\n        startButton.setEnabled(false);\\n        stopButton.setEnabled(true);\\n        statusLabel.setText(\"正在准备正文搜索……\");\\n        currentWorker.execute();\\n'''

correct = '''        savePreferences(categories);\\n        resultModel.clear();\\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories);\\n        startButton.setEnabled(false);\\n        stopButton.setEnabled(true);\\n        statusLabel.setText(\"正在准备正文搜索……\");\\n        currentPathLabel.setText(\"当前：准备扫描……\");\\n        currentWorker.execute();\\n'''

if wrong not in src:
    raise SystemExit('Could not locate the v1.2.7 startSearch patch pattern to repair')

src = src.replace(wrong, correct, 1)
src = src.replace('1.2.7', '1.2.8')

code = compile(src, 'optimize_content_v128_folder_batches.py', 'exec')
exec(code, {'__name__': '__main__'})
