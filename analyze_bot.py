#!/usr/bin/env python
# -*- coding: utf-8 -*-
# analyze_bot.py
"""
Command-line tool for running bot analysis
Usage: python analyze_bot.py [--quick] [--days 30] [--save]
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Setup path
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis import BotAnalyzer
from db import Database
import config as CFG


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('./logs/analysis.log')
        ]
    )
    return logging.getLogger(__name__)


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description='Analyze bot performance and generate reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_bot.py                 # Full analysis
  python analyze_bot.py --quick         # Quick health check
  python analyze_bot.py --days 7        # Last 7 days
  python analyze_bot.py --quick --save  # Quick check + save
        """
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick health check instead of full analysis'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='Save report to file'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Custom output filename'
    )

    args = parser.parse_args()

    # Setup logging
    log = setup_logging()

    try:
        # Connect to database
        log.info("Connecting to database...")
        db = Database()
        
        # Create analyzer
        log.info("Initializing analyzer...")
        analyzer = BotAnalyzer(db=db, config=CFG, log=log)

        # Run analysis
        if args.quick:
            log.info("Running quick health check...")
            report = analyzer.run_quick_check()
        else:
            log.info(f"Running full analysis for last {args.days} days...")
            report = analyzer.run_full_analysis(days=args.days)

        # Print report
        print(report)

        # Save if requested
        if args.save:
            filepath = analyzer.save_report_to_file(report, args.output)
            if filepath:
                print(f"\n✅ Report saved to: {filepath}")

        log.info("Analysis complete")

    except Exception as e:
        log.error(f"Error during analysis: {e}", exc_info=True)
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
