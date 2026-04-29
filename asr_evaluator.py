import os
import time
import json
import difflib
from typing import Dict, List, Optional, Tuple
from asr_processor import ASRProcessor, ASRBackend


class ASREvaluator:
    def __init__(self, asr_processor: Optional[ASRProcessor] = None):
        self.asr_processor = asr_processor or ASRProcessor()
        self.test_results = []
    
    def calculate_wer(self, reference: str, hypothesis: str) -> float:
        """
        计算词错误率 (Word Error Rate, WER)
        对于中文，以字符为单位计算
        """
        ref_chars = list(reference.replace(' ', ''))
        hyp_chars = list(hypothesis.replace(' ', ''))
        
        if not ref_chars:
            return 0.0 if not hyp_chars else 1.0
        
        d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]
        
        for i in range(len(ref_chars) + 1):
            d[i][0] = i
        for j in range(len(hyp_chars) + 1):
            d[0][j] = j
        
        for i in range(1, len(ref_chars) + 1):
            for j in range(1, len(hyp_chars) + 1):
                cost = 0 if ref_chars[i-1] == hyp_chars[j-1] else 1
                d[i][j] = min(
                    d[i-1][j] + 1,
                    d[i][j-1] + 1,
                    d[i-1][j-1] + cost
                )
        
        return d[len(ref_chars)][len(hyp_chars)] / len(ref_chars)
    
    def calculate_cer(self, reference: str, hypothesis: str) -> float:
        """
        计算字符错误率 (Character Error Rate, CER)
        与WER相同，中文以字符为单位
        """
        return self.calculate_wer(reference, hypothesis)
    
    def calculate_accuracy(self, reference: str, hypothesis: str) -> float:
        """
        计算准确率 (1 - CER)
        """
        return 1.0 - self.calculate_cer(reference, hypothesis)
    
    def test_single_audio(
        self, 
        audio_path: str, 
        reference_text: str,
        backend: Optional[str] = None,
        preprocess: bool = True
    ) -> Dict:
        """
        测试单个音频文件
        """
        print(f"\n{'='*70}")
        print(f"测试音频: {os.path.basename(audio_path)}")
        print(f"参考文本: {reference_text}")
        print(f"{'='*70}")
        
        start_time = time.time()
        
        result = self.asr_processor.transcribe(
            audio_path, 
            backend=backend,
            preprocess=preprocess
        )
        
        total_time = time.time() - start_time
        
        hypothesis_text = result.get('full_text', '')
        
        wer = self.calculate_wer(reference_text, hypothesis_text)
        cer = self.calculate_cer(reference_text, hypothesis_text)
        accuracy = self.calculate_accuracy(reference_text, hypothesis_text)
        
        test_result = {
            'audio_file': os.path.basename(audio_path),
            'reference': reference_text,
            'hypothesis': hypothesis_text,
            'success': result.get('success', False),
            'backend_used': result.get('backend_used', 'unknown'),
            'response_time': result.get('response_time', total_time),
            'total_time': total_time,
            'wer': wer,
            'cer': cer,
            'accuracy': accuracy,
            'passed': accuracy >= 0.95
        }
        
        self.test_results.append(test_result)
        
        print(f"\n识别结果: {hypothesis_text}")
        print(f"准确率: {accuracy*100:.2f}%")
        print(f"字符错误率 (CER): {cer*100:.2f}%")
        print(f"响应时间: {test_result['response_time']:.2f}秒")
        print(f"总耗时: {total_time:.2f}秒")
        print(f"后端: {test_result['backend_used']}")
        print(f"状态: {'✅ 通过' if test_result['passed'] else '❌ 未通过'}")
        
        return test_result
    
    def run_batch_test(
        self, 
        test_cases: List[Dict],
        backend: Optional[str] = None,
        preprocess: bool = True
    ) -> Dict:
        """
        批量运行测试
        
        test_cases格式:
        [
            {'audio_path': 'path/to/audio1.wav', 'reference': '参考文本1'},
            {'audio_path': 'path/to/audio2.wav', 'reference': '参考文本2'},
            ...
        ]
        """
        print(f"\n{'#'*70}")
        print(f"开始批量测试 - 共 {len(test_cases)} 个测试用例")
        print(f"{'#'*70}")
        
        self.test_results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n测试用例 {i}/{len(test_cases)}")
            self.test_single_audio(
                test_case['audio_path'],
                test_case['reference'],
                backend=backend,
                preprocess=preprocess
            )
        
        return self.generate_summary_report()
    
    def generate_summary_report(self) -> Dict:
        """
        生成测试总结报告
        """
        if not self.test_results:
            return {'message': 'No test results available'}
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        success_calls = sum(1 for r in self.test_results if r['success'])
        
        avg_accuracy = sum(r['accuracy'] for r in self.test_results) / total_tests
        avg_response_time = sum(r['response_time'] for r in self.test_results) / total_tests
        avg_total_time = sum(r['total_time'] for r in self.test_results) / total_tests
        
        backends_used = {}
        for r in self.test_results:
            backend = r['backend_used']
            backends_used[backend] = backends_used.get(backend, 0) + 1
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'pass_rate': passed_tests / total_tests * 100,
                'success_calls': success_calls,
                'call_success_rate': success_calls / total_tests * 100
            },
            'metrics': {
                'average_accuracy': avg_accuracy * 100,
                'average_response_time': avg_response_time,
                'average_total_time': avg_total_time
            },
            'backends': backends_used,
            'detailed_results': self.test_results
        }
        
        print(f"\n{'='*70}")
        print(f"测试总结报告")
        print(f"{'='*70}")
        print(f"总测试数: {total_tests}")
        print(f"通过数: {passed_tests}")
        print(f"失败数: {total_tests - passed_tests}")
        print(f"通过率: {report['summary']['pass_rate']:.2f}%")
        print(f"平均准确率: {report['metrics']['average_accuracy']:.2f}%")
        print(f"平均响应时间: {report['metrics']['average_response_time']:.2f}秒")
        print(f"平均总耗时: {report['metrics']['average_total_time']:.2f}秒")
        print(f"使用的后端: {backends_used}")
        print(f"{'='*70}")
        
        return report
    
    def save_report(self, report: Dict, output_path: str = "asr_test_report.json"):
        """
        保存测试报告到文件
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n测试报告已保存到: {output_path}")


def create_demo_test_cases() -> List[Dict]:
    """
    创建演示用的测试用例
    """
    return [
        {
            'audio_path': '',
            'reference': '今天天气真的很好，我来到了这家新开的咖啡店。'
        }
    ]


if __name__ == "__main__":
    print("ASR 评估器初始化完成")
    print("使用方法:")
    print("1. 创建 ASREvaluator 实例")
    print("2. 使用 test_single_audio() 测试单个音频")
    print("3. 使用 run_batch_test() 批量测试")
    print("4. 使用 generate_summary_report() 生成报告")
