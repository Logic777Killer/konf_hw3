import argparse
import re
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


class ConfigParser:
    def __init__(self):
        self.constants = {}

    def validate_name(self, name):
        """Проверяет, что имя соответствует синтаксису."""
        if not re.match(r'^[_a-zA-Z][_a-zA-Z0-9]*$', name):
            raise ValueError(f"Недопустимое имя: {name}")
        return name

    def format_value(self, value, indent=4):
        """Форматирует значение в соответствии с синтаксисом конфигурационного языка."""
        if isinstance(value, str):
            if value.startswith("$(") and value.endswith(")"):
                print(f"Обрабатывается выражение: {value}")
                evaluated = self.evaluate_expression(value)
                print(f"Результат вычисления: {evaluated}")
                return str(evaluated)
            return f"'{value}'"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            items = [self.format_value(item, indent) for item in value]
            return f"{{ {', '.join(items)} }}"
        elif isinstance(value, dict):
            return self.format_dict(value, indent)
        else:
            raise ValueError(f"Неподдерживаемый тип значения: {type(value)}")

    def format_dict(self, data, indent=4):
        """Форматирует словарь в синтаксис конфигурационного языка."""
        lines = []
        nested_indent = " " * indent
        for key, value in data.items():
            self.validate_name(key)
            formatted_value = self.format_value(value, indent + 4)
            lines.append(f"{nested_indent}{key} : {formatted_value},")
        return f"{{\n{chr(10).join(lines)}\n{' ' * (indent - 4)}}}"

    def process_defines(self, defines):
        """Обрабатывает объявления констант."""
        for key, value in defines.items():
            self.validate_name(key)
            if isinstance(value, (int, float, str)):
                self.constants[key] = value
            else:
                raise ValueError(f"Недопустимое значение для константы {key}: {value}")

    def evaluate_expression(self, expr):
        """Вычисляет выражение в постфиксной форме."""
        expr_content = expr.strip('$()\'"')
        tokens = expr_content.split()
        stack = []
        for token in tokens:
            if token in self.constants:
                stack.append(self.constants[token])
            elif re.match(r'^-?\d+(\.\d+)?$', token):  # Число
                stack.append(float(token) if '.' in token else int(token))
            elif token == 'mod':
                if len(stack) < 2:
                    raise ValueError("Недостаточно операндов для mod")
                b = stack.pop()
                a = stack.pop()
                stack.append(a % b)
            elif token == 'max':
                if len(stack) < 2:
                    raise ValueError("Недостаточно операндов для max")
                b = stack.pop()
                a = stack.pop()
                stack.append(max(a, b))
            elif token in ['+', '-', '*']:
                if len(stack) < 2:
                    raise ValueError("Недостаточно операндов в выражении")
                b = stack.pop()
                a = stack.pop()
                if token == '+':
                    stack.append(a + b)
                elif token == '-':
                    stack.append(a - b)
                elif token == '*':
                    stack.append(a * b)
            else:
                raise ValueError(f"Неизвестный токен: {token}")
        if len(stack) != 1:
            raise ValueError(f"Некорректное выражение: {expr}")
        print(f"Вычисляем выражение: {expr_content}")
        return stack[0]

    def convert_to_custom_language(self, data, indent=4):
        """Преобразует YAML данные в учебный конфигурационный язык."""
        lines = []

        # Сохраняем многострочные комментарии из верхнего уровня
        if hasattr(data, 'ca') and data.ca.comment:
            top_comments = data.ca.comment[1]  # Получаем список комментариев
            if top_comments:
                lines.append("=begin")
                for comment in top_comments:
                    if isinstance(comment, str):
                        cleaned_comment = comment.lstrip("# ").strip()  # Убираем # и пробелы
                        lines.append(cleaned_comment)
                    elif hasattr(comment, "value"):  # Если это CommentToken
                        cleaned_comment = comment.value.lstrip("# ").strip()  # Убираем # и пробелы
                        lines.append(cleaned_comment)
                lines.append("=cut")
                lines.append("")  # Пустая строка после комментариев

        # Обработка секции 'define'
        if 'define' in data:
            defines = data.pop('define')
            self.process_defines(defines)
            for key, value in defines.items():
                lines.append(f"(define {key} {value});")
            lines.append("")  # Пустая строка после секции 'define'

        # Обработка остальных данных
        for key, value in data.items():
            # Извлекаем комментарии, если есть
            if hasattr(data, 'ca') and key in data.ca.items and data.ca.items[key]:
                comment = data.ca.items[key][2]  # Комментарий после ключа
                if comment:
                    if isinstance(comment, str):
                        cleaned_comment = comment.lstrip("# ").strip()
                        lines.append(f":: {cleaned_comment}")
                    elif hasattr(comment, "value"):  # Если это CommentToken
                        cleaned_comment = comment.value.lstrip("# ").strip()
                        lines.append(f":: {cleaned_comment}")

            self.validate_name(key)
            formatted_value = self.format_value(value, indent)
            lines.append(f"{key} : {formatted_value};")
            lines.append("")  # Сохраняем пустые строки между секциями

        # Убираем лишние пустые строки
        return "\n".join(line for line in lines if line.strip() or line == "")


def parse_yaml_with_comments(file_path):
    """Считывает YAML файл с сохранением комментариев."""
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.load(f)
    except FileNotFoundError:
        raise ValueError(f"Файл {file_path} не найден.")
    except Exception as e:
        raise ValueError(f"Ошибка парсинга YAML: {e}")


def main():
    parser = argparse.ArgumentParser(description="Конвертер YAML в учебный конфигурационный язык.")
    parser.add_argument("-i", "--input", required=True, help="Путь к входному YAML файлу.")
    parser.add_argument("-o", "--output", required=True, help="Путь к выходному файлу.")
    args = parser.parse_args()

    try:
        yaml_data = parse_yaml_with_comments(args.input)
        config_parser = ConfigParser()
        output_data = config_parser.convert_to_custom_language(yaml_data)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_data)
        print(f"Файл успешно создан: {args.output}")
    except ValueError as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    main()
