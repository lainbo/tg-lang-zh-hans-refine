#!/usr/bin/env python3
"""在临时项目中执行真实 CLI，验证增量、错误阻断和 .strings 往返。"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from _common import dump_strings, parse_strings


def main():
    checks = []
    commands = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    with tempfile.TemporaryDirectory(prefix='tg-refine-e2e-') as tmp:
        root = Path(tmp)
        shutil.copytree(ROOT / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'docs', root / 'docs')
        work = root / 'work/ios'
        raw = root / 'data/ios/raw'
        dist = root / 'dist/ios/zh-Hans-custom.strings'
        for path in (work, raw, root / 'data/ios/parsed', dist.parent):
            path.mkdir(parents=True, exist_ok=True)

        def write(path, data):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        def read(path):
            return json.loads(path.read_text(encoding='utf-8'))

        def run(script, *args, ok=True):
            proc = subprocess.run([sys.executable, str(root / 'scripts' / script), 'ios', *map(str, args)],
                                  cwd=root, text=True, capture_output=True)
            commands.append({'script': script, 'args': [str(a).replace(str(root), '<fixture>') for a in args],
                             'returncode': proc.returncode,
                             'output': (proc.stdout + proc.stderr).replace(str(root), '<fixture>')})
            check(f'{script} {"通过" if ok else "阻断"} #{len(commands)}', (proc.returncode == 0) == ok)

        old = {'stable': '%@ has %d items.', 'changed': 'Old value', 'removed': 'Remove me',
               'syntax': 'https://example.com/a // /* literal */ "quote"\nnext', 'space': ' '}
        old_final = {'stable': '%@ 有 %d 个项目。', 'changed': '旧值', 'removed': '将删除',
                     'syntax': 'https://example.com/a // /* literal */ "引号"\n下一行', 'space': ' '}
        write(work / 'merged.json', {k: {'en': v} for k, v in old.items()})
        write(work / 'translated.json', {k: {'final': v, 'source': 'fresh'} for k, v in old_final.items()})
        previous_translated = read(work / 'translated.json')
        previous_translated['stable'].update(source='adopt', note='adopt:历史精修')
        write(work / 'translated.json', previous_translated)
        (raw / 'en.strings').write_text(dump_strings(old))
        (raw / 'official-zh.strings').write_text(dump_strings(old_final))
        (raw / 'zhcncc.strings').write_text(dump_strings({'changed': '社区旧译'}))
        (raw / 'ref-current-refined.strings').write_text(dump_strings({'changed': '过期精修副本'}))
        reference_bytes = {p.name: p.read_bytes() for p in raw.glob('*.strings') if p.name != 'en.strings'}
        dist.write_text(dump_strings(old_final))
        old_dist = dist.read_bytes()
        # 历史尾片应由归档隔离。
        write(work / 'translated.part99.json', {'removed': {'final': '旧片', 'source': 'fresh'}})
        new = {k: v for k, v in old.items() if k != 'removed'}
        new.update(changed='New value', added='Save %.2d%% for %1$@')
        en = root / 'download-en.strings'
        en.write_text(dump_strings(new))
        run('prepare_update.py', '--en', en, '--chunk', 1)
        update = read(work / 'update.json')
        check('新增/变化/删除分类', update['added'] == ['added'] and update['changed'] == ['changed'] and update['removed'] == ['removed'])
        check('旧片归档', not (work / 'translated.part99.json').exists() and (work / update['archive'] / 'work/translated.part99.json').exists())
        check('成品备份与原件完整', (work / update['archive'] / 'dist/zh-Hans-custom.strings').read_bytes() == old_dist == dist.read_bytes())
        check('未变英文逐字复用', read(work / 'translated.reused.json')['stable']['final'] == old_final['stable'])
        check('历史来源与备注保持原意', read(work / 'translated.reused.json')['stable'] == previous_translated['stable'])
        check('旧英文上下文', read(work / 'to-translate.json')['changed']['previous_en'] == 'Old value')
        check('默认基准只含英文', read(work / 'merged.json') == {k: {'en': v} for k, v in new.items()})
        check('默认审校输入不含中文候选', read(work / 'to-translate.json') == {
            'added': {'en': new['added']}, 'changed': {'en': new['changed'], 'previous_en': old['changed']}})
        check('旧英文与精修译文单独配对保存', read(work / 'translation-memory.json') == {
            k: {'en': old[k], 'final': old_final[k]} for k in old})
        check('历史参考文件逐字保留', all((raw / name).read_bytes() == content for name, content in reference_bytes.items()))
        check('来源记录只要求英文', set(update['sources']) == {'en'})
        run('merge_parts.py', ok=False)
        for part in work.glob('to-translate.part*.json'):
            values = {'added': '%1$@ 可节省 %.2d%%', 'changed': '您看到的新值...'}
            write(work / part.name.replace('to-translate', 'translated'),
                  {k: {'final': values[k], 'source': 'fresh'} for k in read(part)})
        run('import_from_ai.py', '--part', 1)
        run('merge_parts.py')
        initial = read(work / 'translated.json')
        run('normalize.py')
        check('dry-run 不改主文件', read(work / 'translated.json') == initial)
        run('normalize.py', '--apply')
        final = read(work / 'translated.json')
        check('规范化修改主文件且备份', final['changed']['final'] == '你看到的新值…' and read(work / 'translated.json.bak') == initial)
        run('import_from_ai.py')
        run('diff_report.py', '--update')
        report = (work / 'update-report.html').read_text()
        check('审核报告展示原文变化与精修对照', all(x in report for x in ['新增文案', '英文变化', '旧值', 'New value'])
              and all(x not in report for x in ['社区旧译', '过期精修副本', '<th>official_zh</th>']))
        run('build_strings.py')
        expected = {**old_final, 'changed': '你看到的新值…', 'added': '%1$@ 可节省 %.2d%%'}
        del expected['removed']
        check('最终覆盖与 .strings 无损往返', parse_strings(dist.read_text()) == expected)
        check('单片与全量验证工件独立', (work / 'validation.part01.json').exists() and read(work / 'validation.json')['problem_count'] == 0)
        good_dist = dist.read_bytes()
        good_master = (work / 'translated.json').read_bytes()
        write(work / 'translated.part99.json', {})
        run('merge_parts.py', ok=False)
        check('旧片残留阻断且保留主文件', (work / 'translated.json').read_bytes() == good_master)
        (work / 'translated.part99.json').unlink()
        reused = read(work / 'translated.reused.json')
        write(work / 'translated.reused.json', {**reused, 'added': final['added']})
        run('merge_parts.py', ok=False)
        write(work / 'translated.reused.json', reused)
        for name, change in [
            ('缺译', lambda d: d.pop('added')),
            ('多译', lambda d: d.update(extra={'final': '多余', 'source': 'fresh'})),
            ('空译文', lambda d: d['added'].update(final='')),
            ('非法来源', lambda d: d['added'].update(source=[])),
            ('非法备注', lambda d: d['added'].update(note=3)),
            ('占位符丢失', lambda d: d['added'].update(final='%1$@ 节省 %%')),
            ('百分号转义丢失', lambda d: d['added'].update(final='%1$@ 节省 %.2d%')),
            ('无编号参数换序', lambda d: d['stable'].update(final='%d 个项目属于 %@')),
        ]:
            invalid = json.loads(json.dumps(final))
            change(invalid)
            write(work / 'translated.json', invalid)
            run('import_from_ai.py', ok=False)
            run('build_strings.py', ok=False)
            check(name + '阻断且保留成品', dist.read_bytes() == good_dist)
        write(work / 'translated.json', [])
        run('import_from_ai.py', ok=False)
        run('build_strings.py', ok=False)
        write(work / 'translated.json', final)
        run('prepare_update.py', '--en', en)
        check('无变化增量为空', read(work / 'to-translate.json') == {})
        run('merge_parts.py')
        run('build_strings.py')
        check('无变化成品逐字稳定', dist.read_bytes() == good_dist)

        shutil.rmtree(work)
        work.mkdir()
        run('merge.py')
        run('export_for_ai.py', '--chunk', 2)
        check('首次全量输入只含英文', read(work / 'to-translate.json') == {k: {'en': v} for k, v in new.items()})
        # 旧轮次基准带有候选列时，导出也遵守当前输入约定。
        write(work / 'merged.json', {k: {'en': v, 'official_zh': '官方候选', 'refs': {'zhcncc': '社区候选'}}
                                    for k, v in new.items()})
        run('export_for_ai.py', '--chunk', 2)
        check('重新导出旧基准不带入参考列', read(work / 'to-translate.json') == {k: {'en': v} for k, v in new.items()})
        for part in work.glob('to-translate.part*.json'):
            write(work / part.name.replace('to-translate', 'translated'), {k: final[k] for k in read(part)})
        run('merge_parts.py')
        run('diff_report.py')
        run('build_strings.py')
        check('首次全量流程可打包', dist.read_bytes() == good_dist)

        shutil.rmtree(root / 'data/ios/parsed')
        for name in reference_bytes:
            (raw / name).unlink()
        run('parse_strings.py')
        run('merge.py')
        run('prepare_update.py', '--en', en)
        check('只有英文源也能准备更新', read(work / 'to-translate.json') == {} and
              list(raw.glob('*.strings')) == [raw / 'en.strings'])
        run('merge_parts.py')
        run('build_strings.py')
        check('无参考包更新保持成品一致', dist.read_bytes() == good_dist)

    result = {'passed': True, 'check_count': len(checks), 'checks': checks, 'commands': commands}
    output = ROOT / 'work/maintenance/e2e-result.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'端到端验证通过：{len(checks)} 项检查；结果 → {output}')


if __name__ == '__main__':
    main()
