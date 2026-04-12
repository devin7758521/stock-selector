# -*- coding: utf-8 -*-
"""
LLM分析配置管理

集中管理LLM分析器的所有配置参数，包括权重分配、API配置等。

Copyright (c) 2026 stock selector. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class WeightsConfig:
    """权重配置"""
    llm: float = 0.5
    ai: float = 0.3
    technical: float = 0.2

    def __post_init__(self):
        total = self.llm + self.ai + self.technical
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"权重总和必须为1.0，当前为{total}")


@dataclass
class LLMConfig:
    """LLM分析器配置"""
    api_key: Optional[str] = None
    model: str = "local"
    weights: WeightsConfig = field(default_factory=WeightsConfig)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'LLMConfig':
        """
        从字典创建配置对象

        Args:
            config: 配置字典

        Returns:
            LLMConfig实例
        """
        api_key = config.get('api_key')
        model = config.get('model', 'local')

        weights_dict = config.get('weights', {})
        weights = WeightsConfig(
            llm=weights_dict.get('llm', 0.5),
            ai=weights_dict.get('ai', 0.3),
            technical=weights_dict.get('technical', 0.2)
        )

        return cls(api_key=api_key, model=model, weights=weights)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'api_key': self.api_key,
            'model': self.model,
            'weights': {
                'llm': self.weights.llm,
                'ai': self.weights.ai,
                'technical': self.weights.technical
            }
        }


@dataclass
class AnalyzerConfig:
    """分析器通用配置"""
    technical_weight: float = 0.20
    fundamental_weight: float = 0.30
    news_weight: float = 0.25
    policy_weight: float = 0.15
    market_weight: float = 0.10

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'AnalyzerConfig':
        """
        从字典创建配置对象

        Args:
            config: 配置字典

        Returns:
            AnalyzerConfig实例
        """
        return cls(
            technical_weight=config.get('technical_weight', 0.20),
            fundamental_weight=config.get('fundamental_weight', 0.30),
            news_weight=config.get('news_weight', 0.25),
            policy_weight=config.get('policy_weight', 0.15),
            market_weight=config.get('market_weight', 0.10)
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'technical_weight': self.technical_weight,
            'fundamental_weight': self.fundamental_weight,
            'news_weight': self.news_weight,
            'policy_weight': self.policy_weight,
            'market_weight': self.market_weight
        }
