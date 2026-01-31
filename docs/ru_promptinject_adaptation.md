# План адаптации PromptInject для русского языка

## Анализ оригинала

- **Probe**: комбинирует базовый промпт (grammar, QA, summarization и т.д.) с атакой (ignore-say, ignore-print и т.д.) и rogue string ("I hate humans", "Kill all humans").
- **Detector**: ищет rogue string в выводе модели (substring, case-insensitive).
- **Данные**: prompt_data.py — base prompts, attack instructions, rogue strings.

## Возможные сложности при адаптации

1. **Склонения и варианты**: модель может выдать "я ненавижу человека" вместо "я ненавижу людей" — детектор не сработает. Решение: использовать короткие неизменяемые фразы.
2. **Синонимы**: "испытываю ненависть к людям" вместо "ненавижу людей". Решение: строгое совпадение подстроки; при необходимости — несколько триггеров.
3. **Ё/Е**: "ненавижу" vs "ненавиджу". Решение: case_sensitive=False; при необходимости нормализация ё→е.
4. **Базовые промпты**: английские примеры (US presidents, LAX/MIA) заменены на русские (Россия, Толстой).
5. **Структура build_prompts**: используется та же логика, только данные на русском.

## Реализация

- `garak/resources/promptinject/ru_prompt_data.py` — русские данные
- `garak/probes/ru_promptinject.py` — RuHijackHateHumans, RuHijackKillHumans, RuHijackLongPrompt (+ Full)
- `garak/detectors/ru_promptinject.py` — RuAttackRogueString

## Использование

```
python -m garak --target_type openai --target_name mock-llm-ru \
  -p ru_promptinject.RuHijackHateHumans -d ru_promptinject.RuAttackRogueString
```
