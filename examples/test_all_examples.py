#!/usr/bin/env python3
"""
LightAPI Examples Test Suite

This script tests all examples in the examples/ directory to ensure they:
1. Can be imported without errors
2. Have valid syntax
3. Can start a server (basic validation)
4. Have proper dependencies

Usage:
    python examples/test_all_examples.py
"""

import os
import sys
import subprocess
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Tuple


class ExampleTester:
    """Test all LightAPI examples for basic functionality."""
    
    def __init__(self):
        self.examples_dir = Path(__file__).parent
        self.results = {}
        self.errors = []
        
    def find_example_files(self) -> List[Path]:
        """Find all Python example files."""
        examples = []
        for file_path in self.examples_dir.glob("*.py"):
            if file_path.name != "__init__.py" and not file_path.name.startswith("test_"):
                examples.append(file_path)
        return sorted(examples)
    
    def test_import(self, file_path: Path) -> Tuple[bool, str]:
        """Test if the example can be imported."""
        try:
            spec = importlib.util.spec_from_file_location("example", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return True, "Import successful"
        except Exception as e:
            return False, f"Import error: {str(e)}"
    
    def test_syntax(self, file_path: Path) -> Tuple[bool, str]:
        """Test if the example has valid Python syntax."""
        try:
            with open(file_path, 'r') as f:
                compile(f.read(), str(file_path), 'exec')
            return True, "Syntax valid"
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"
        except Exception as e:
            return False, f"Parse error: {str(e)}"
    
    def test_basic_functionality(self, file_path: Path) -> Tuple[bool, str]:
        """Test basic functionality by running the example briefly."""
        try:
            # Run the example with a timeout to check if it starts properly
            result = subprocess.run(
                [sys.executable, str(file_path)],
                capture_output=True,
                text=True,
                timeout=5,  # 5 second timeout
                cwd=str(self.examples_dir.parent)  # Run from project root
            )
            
            # Check if it started without critical errors
            if "Server running at" in result.stdout or "Traceback" not in result.stderr:
                return True, "Basic functionality OK"
            else:
                return False, f"Runtime error: {result.stderr[:200]}"
                
        except subprocess.TimeoutExpired:
            return True, "Started successfully (timeout expected)"
        except Exception as e:
            return False, f"Execution error: {str(e)}"
    
    def test_example(self, file_path: Path) -> Dict:
        """Test a single example file."""
        print(f"Testing {file_path.name}...")
        
        result = {
            "file": file_path.name,
            "import": False,
            "syntax": False,
            "functionality": False,
            "errors": []
        }
        
        # Test import
        import_ok, import_msg = self.test_import(file_path)
        result["import"] = import_ok
        if not import_ok:
            result["errors"].append(f"Import: {import_msg}")
        
        # Test syntax
        syntax_ok, syntax_msg = self.test_syntax(file_path)
        result["syntax"] = syntax_ok
        if not syntax_ok:
            result["errors"].append(f"Syntax: {syntax_msg}")
        
        # Test basic functionality (only if import and syntax are OK)
        if import_ok and syntax_ok:
            func_ok, func_msg = self.test_basic_functionality(file_path)
            result["functionality"] = func_ok
            if not func_ok:
                result["errors"].append(f"Functionality: {func_msg}")
        
        return result
    
    def run_all_tests(self):
        """Run tests on all examples."""
        print("🧪 LightAPI Examples Test Suite")
        print("=" * 50)
        
        example_files = self.find_example_files()
        print(f"Found {len(example_files)} example files")
        print()
        
        for file_path in example_files:
            result = self.test_example(file_path)
            self.results[file_path.name] = result
            
            # Print result
            status = "✅" if all([result["import"], result["syntax"], result["functionality"]]) else "❌"
            print(f"{status} {file_path.name}")
            
            if result["errors"]:
                for error in result["errors"]:
                    print(f"   ⚠️  {error}")
        
        print()
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if all([r["import"], r["syntax"], r["functionality"]]))
        failed = total - passed
        
        print("📊 Test Summary")
        print("=" * 50)
        print(f"Total examples: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print("\n❌ Failed Examples:")
            for name, result in self.results.items():
                if not all([result["import"], result["syntax"], result["functionality"]]):
                    print(f"  - {name}: {', '.join(result['errors'])}")
        
        print("\n🔍 Detailed Results:")
        for name, result in self.results.items():
            status_icons = [
                "✅" if result["import"] else "❌",
                "✅" if result["syntax"] else "❌", 
                "✅" if result["functionality"] else "❌"
            ]
            print(f"  {name}: Import {status_icons[0]} | Syntax {status_icons[1]} | Functionality {status_icons[2]}")


def main():
    """Main function."""
    tester = ExampleTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
