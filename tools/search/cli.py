"""Local requirement-4 CLI: status, query, diagnose, batch, score, gui."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np
from PIL import Image

from tools.image_processing.tool_common import configure_console

from tools.project_paths import B400_OUTPUT_DIR, PROJECT_ROOT
from tools.search.index import SearchIndex
from tools.search.query import load_image, load_mask, create_mask, refine, retrieve, output_base
from tools.search.evaluation import run_batch, score_batch
from tools.search.mask_quality import review_message


def main(argv=None):
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feature-dir', type=Path, default=B400_OUTPUT_DIR)
    parser.add_argument('--project-root', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--run-id', help='Completed run; default summary.json run_id')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    commands.add_parser('gui')
    query = commands.add_parser('query')
    query.add_argument('--image', type=Path, required=True)
    query.add_argument('--mask', type=Path)
    query.add_argument('--bbox', type=int, nargs=4, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    query.add_argument('--strokes', type=Path, help='PNG uint8: keep=1, remove=0, unmarked=255')
    query.add_argument('--iterations', type=int, default=5)
    query.add_argument('--include-self', action='store_true')
    query.add_argument('--output-dir', type=Path)
    diagnose = commands.add_parser('diagnose', help='Check a saved query and explain mask/vector/ranking differences')
    diagnose.add_argument('--query-dir', type=Path, required=True)
    diagnose.add_argument('--output-dir', type=Path)
    batch = commands.add_parser('batch')
    batch.add_argument('--manifest', type=Path, required=True)
    batch.add_argument('--output-dir', type=Path)
    score = commands.add_parser('score')
    score.add_argument('--batch', type=Path, required=True, help='batch.json')
    score.add_argument('--judgments', type=Path, required=True)
    score.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        cv2.setNumThreads(1)
        if args.command == 'score':
            report = score_batch(args.batch, args.judgments, output_base(args.project_root, args.output_dir), args.project_root)
            print(json.dumps(report['overall'], ensure_ascii=False, indent=2))
            return 0
        if args.command == 'gui':
            from tools.search.gui import launch
            launch(args.feature_dir, args.run_id, args.project_root)
            return 0
        index = SearchIndex(args.feature_dir, args.run_id, args.project_root)
        if args.command == 'status':
            print(json.dumps({key: value for key, value in index.describe().items()
                              if key != 'candidate_unique_contents'}, indent=2))
        elif args.command == 'diagnose':
            from tools.search.diagnostics import diagnose as diagnose_saved
            report = diagnose_saved(index, args.query_dir, args.output_dir)
            passed = (all(item['matches'] for item in report['identity'].values())
                      and all(report['configuration_matches'].values())
                      and all(item['exact_match'] for item in report['normalization'].values())
                      and report['reranking']['all_saved_hits_match']
                      and report['reranking']['excluded_self_count_matches'])
            print(json.dumps(dict(verified=passed, output_directory=report['output_directory'],
                                  normalization=report['normalization'], reranking=report['reranking'],
                                  reference_mask_available=report['reference_mask']['available']), ensure_ascii=False, indent=2))
            return 0 if passed else 1
        elif args.command == 'batch':
            folder = run_batch(index, args.manifest, args.output_dir)
            print(folder)
            from tools.search.index import read_json
            return int(any(q['status'] != 'success' for q in read_json(folder/'batch.json')['queries']))
        else:
            if args.mask and args.bbox:
                raise ValueError('Choose --mask or --bbox as initialization')
            output_base(args.project_root, args.output_dir)
            image = load_image(args.image)
            mask, info = load_mask(args.mask, image.rgb) if args.mask else create_mask(image.rgb, args.bbox, args.iterations)
            strokes = None
            if args.strokes:
                with Image.open(args.strokes) as source:
                    strokes = np.array(source)
                mask, seconds = refine(image.rgb, mask, strokes, args.iterations)
                info.update(mask_seconds=info['mask_seconds']+seconds, refinement='hard strokes')
            result = retrieve(index, image, mask, info, args.output_dir, not args.include_self, strokes)
            print(review_message(result['query']['mask_diagnostics']))
            print(json.dumps({k: result[k] for k in ['query_id', 'output_directory', 'timings', 'excluded_self_files',
                                                      'candidate_files', 'shortfall_reason']}, indent=2))
            for hit in result['results']:
                print(f'{hit["rank"]}. {hit["filename"]}  D={hit["distance"]:.9f}  {hit["orientation"]}  label={hit["label"]}')
        return 0
    except Exception as exc:
        print(f'Search error: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
