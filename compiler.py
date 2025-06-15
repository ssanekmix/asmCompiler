def multi_split(s, seps):
    # передаем строку и разделители
    # "a=10;b=5", [';', '='] → ["a", "10", "b", "5"]
    parts = []
    curr = ""
    for char in s:
        if char in seps:
            if len(curr.strip()) > 0:
                parts.append(curr.strip())
            curr = ""
        else:
            curr += char
    # вдруг что-то осталось
    if len(curr.strip()) > 0:
        parts.append(curr.strip())
    return parts

with open("code1.ww","r") as f:
    code = f.read() 
c = code.replace("\n", "").replace("\t", "")
firstSplit = multi_split(c, [';', '{']) # нужно разбиение построчно, а не посимвольно
# a=10;b=5;if(a<10){print b;}
# -> ["a=10", "b=5", "if(a<10)", "print b;", "}"]

spec = ['-', '+', '=', '/', '*', '<', '>', '%', '&', '|', ' ', '(', ')', '#', '$', '!']
vars = []
asm_code = [] # хранить ассемблерный код
asm_data = [] # будем хранить объявления переменных
vars_declared = set() 

label_counter = 0 # счетчик для меток
if_labels = [] # стек меток конца каждого открытого if

string_counter = 0

string_vars = set() #имена переменных-буферов

# Преобразование списка токенов из инфиксной нотации в обратную польскую
def infix_to_postfix(tokens):
    """
    Преобразует выражение из инфиксной нотации в обратную польскую запись, чтобы потом можно было легко выполнить вычисления на стековом процессоре (как в ассемблере).
    a + b * c -> a b c * +
    (a + b) * c -> a b + c *
    """
    precedence = {
        '||': 1, '&&': 2,
        '==': 3, '!=': 3, '<': 3, '>': 3, '<=': 3, '>=': 3,
        '+': 4, '-': 4,
        '*': 5, '/': 5, '%': 5,
    } # приоритет операций( чем больше тем круче)
    output = [] # на вывод
    stack = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if i + 1 < len(tokens) and tok + tokens[i+1] in precedence:
            # если текущий и следующий символ образуют известный оператор то объединяем их
            tok = tok + tokens[i+1]
            i += 1
        if tok == '(':
            stack.append(tok)
        elif tok == ')':
            # выталкиваем все элементы из стека до ( и добавляем их в output
            while len(stack) > 0 and stack[-1] != '(':
                output.append(stack.pop())
                # stack.pop возвращает последний элемент
            stack.pop()  # убираем '('
        elif tok in precedence:
            # выталкиваем операторы с >= приоритетом
            while len(stack) > 0 and stack[-1] != '(' and precedence[stack[-1]] >= precedence[tok]:
                # пока верх стека имеет приоритет ≥ текущего оператора , выталкиваем его в output
                output.append(stack.pop())
                # stack.pop возвращает последний элемент
            stack.append(tok)
        else:
            # если просто операнд
            output.append(tok)
        i += 1
    # оставшиеся операторы из стека
    while stack:
        output.append(stack.pop())

    return output

def extract_if_condition(tokens):
    """
    Извлечение условий из команды if
      ['if','d','<','10',':','{', ...] → ['d','<','10']
    Функция ожидает что встретится символ : который разделяет условие от тела блока
    """
    assert tokens and tokens[0] == 'if'
    # если tokens - пустая строка или tokens[0] не 'if' то выкенет ошибку
    if ':' in tokens:
        idx = tokens.index(':')
        return tokens[1:idx] # от второго элемента до : не включительно
    else:
        # если файл был без : то возвращаем все что после if
        return tokens[1:]


def rpn_to_masm(tokens):
    """
    Преобразует выражение в постфиксной записи в ассемблерный код 
    
    tokens: list[str] — RPN-последовательность, например ['a','b','+','a','+']
    return: list[str] — строки с инструкциями
    """
    asm = []
    for tok in tokens:
        # убираем слева минус и проверяем на число
        if tok.lstrip('-').isdigit():
            asm.append(f"    push {tok}") # если это просто число то кладем в стек
        elif tok.isidentifier():
            # если это имя переменной с учетом проверки python
            # не начинается с цифры, не встроенное ключевое слово
            asm.append(f"    push DWORD PTR [{tok}]")
            # ptr = берем значение по адресу
        else:
            # остается только оператор
            # выталкиваем два верхних значения стека в регистры
            # выполняем операцию
            # результат кладем в стек
            asm.append("    pop ebx")
            asm.append("    pop eax")
            if tok == '+':
                asm.append("    add eax, ebx")
                asm.append("    push eax")
            elif tok == '-':
                asm.append("    sub eax, ebx")
                asm.append("    push eax")
            elif tok == '*':
                asm.append("    imul ebx") # eax = eax * ebx
                asm.append("    push eax")
            elif tok in ('/', '%'):
                asm.append("    cdq") # расширяем eax → edx : eax
                asm.append("    idiv ebx") # делим edx:eax на ebx
                if tok == '/':
                    asm.append("    push eax")  # деление → в EAX
                else:
                    asm.append("    push edx")  # остаток → в EDX
            else:
                raise ValueError(f"Неизвестный оператор: {tok}")
    return asm

def ensure_variable(name: str):
    """
    проверяем, объявлена ли переменная с именем name в секции .data,
    и если нет — добавляем её в vars_declared и в asm_data.
    """
    if name not in vars_declared:
        vars_declared.add(name)
        asm_data.append(f"{name} dd ?")

def new_if_labels():
    # функция генерит уникальный имена меток для одного блока if
    global label_counter
    # ключевое слово global позволяет изменять глобальную переменную
    L = label_counter
    label_counter += 1
    # первая метка - место начала if, вторая - переход на else, третья - конец всего блока
    return f"MakeIf{L}", f"MisIfOrMakeElse{L}", f"MisElse{L}"

def rpn_condition_to_masm(rpn_tokens):
    """
    преобразует условие в обратной польской записи (RPN) в ассемблерный код MASM
    """
    *arith, op = rpn_tokens
    # распаковывает список rpn_tokens отделяя все элементы, кроме последнего в переменную arith а последний — в переменную op
    code = rpn_to_masm(arith)
    # генерим masm код

    # выбираем jmp
    jm_map = {'<':'jl','<=':'jle','>':'jg','>=':'jge','==':'je','!=':'jne'}
    jm = jm_map[op]

    # создаем и собираем метки
    then_lbl, else_lbl, endif_lbl = new_if_labels()
    # f"MakeIf{L}", f"MisIfOrMakeElse{L}", f"MisElse{L}

    # строим код
    code += [
        "    pop ebx",
        "    pop eax",
        "    cmp eax, ebx",
        f"    {jm} {then_lbl}",
        f"    jmp {else_lbl}",
        f"{then_lbl}:",
    ]
    # взяли из стека два числа, сравнили их, если условие истинно то переходим к then_lbl
    # иначе к else_lbl
    return code, else_lbl, endif_lbl

def handle_print(secondSplit):
    """
    обрабатываем команду print:
    """
    rest = secondSplit[1:] # все команды после print
    first = rest[0] # то что нужно вывести

    # строковой литерал в кавычках например ["\"Hello, ww\""](это один элемент массива)
    if first.startswith('"'):
        # собираем весь литерал до закрывающей кавычки
        parts = []
        for tok in rest:
            parts.append(tok)
            if tok.endswith('"'):
                break
        lit = " ".join(parts) # создаем строку через заданный разделитель
        # удаляем внешние кавычки 
        content = lit[1:-1].replace('""', '"').replace('\\"', '"')

        # разбиваем строку по "\n" и добавляем Asm символы перевода строки(0Dh,0Ah) между сегментами
        segs = content.split("\\n") # content = "Line 1\\nLine 2"→ segs = ["Line 1", "Line 2"]
        data_bytes = []
        for idx, seg in enumerate(segs):
            # индекс и элемент массива
            if seg:
                data_bytes.append(f'"{seg}"')
            if idx < len(segs) - 1:
                data_bytes.append("0Dh,0Ah")
        data_bytes.append("0") # segs = ["Line 1", "Line 2"] → data_bytes = ['"Line 1"', '0Dh,0Ah', '"Line 2"','0']

        # создаём уникальную метку и добавляем в .data
        lbl = f"str{len(string_vars)}"
        string_vars.add(lbl)  # чтобы счётчик был уникален
        asm_data.append(f"{lbl} BYTE " + ",".join(data_bytes))

        # в .code — выводим через WriteString
        asm_code.append(f"    lea   edx, {lbl}") # загрузили адрес строки lbl в edx и вывели
        asm_code.append("    call  WriteString")
        return

    # переменная
    if len(rest) == 1 and rest[0].rstrip(',') in string_vars:
        var = rest[0].rstrip(',')
        asm_code.append(f"    lea   edx, {var}") # загрузили адрес переменной в edx и вывели
        asm_code.append("    call  WriteString")
        return

    # арифметическое выражение / число
    rpn = infix_to_postfix(rest)
    seq = rpn_to_masm(rpn)
    asm_code.extend(seq) # добавляет все элементы в конец asm_code
    asm_code.append("    pop   eax")
    asm_code.append("    call  WriteInt") # забрали из стека в eax, вывели

def handle_input(secondSplit):
    # обрабатывает input
    rest = secondSplit[1:]
    # secondSplit = ['input', 'buf,', '64;'] → rest = ['str,', '64;'] → var_token = 'buf'
    var_token = rest[0].rstrip(',') # чистим от запятой
    # если просто число
    if len(rest) == 1:
        var = var_token
        if var not in vars_declared: # объявлена ли?
            vars_declared.add(var)
            asm_data.append(f"{var} dd ?")
        asm_code.append("    call ReadInt") # читаем и перемещаем в eax
        asm_code.append(f"    mov [{var}], eax")
    else:
        # строка с указанием длины
        var = var_token
        maxlen = int(rest[1].rstrip(','))
        if var not in vars_declared: # объявлена ли?
            vars_declared.add(var)
            asm_data.append(f"{var} BYTE {maxlen} DUP(0)")
            string_vars.add(var)
        asm_code.append(f"    lea   edx, {var}") # загружаем адрес строки
        asm_code.append(f"    mov   ecx, {maxlen}")
        asm_code.append("    call ReadString") # читаем

for i in firstSplit:
    secondSplit = i.split(" ") # после первого разбиения взяли строку и засплитили

    if secondSplit[0] == "input":
        handle_input(secondSplit)

    elif secondSplit[0] == "print":
        handle_print(secondSplit)

    elif secondSplit[0] == "if":
        cond_tokens = secondSplit[1:secondSplit.index(':')] # берем все между if и :
        readiSentence = infix_to_postfix(cond_tokens) # обратная польская запись
        ams_if, else_lbl, endif_lbl = rpn_condition_to_masm(readiSentence)
        # в первой переменной asm код, в двух оставшихся метки условия
        asm_code.extend(ams_if) # добавляем asm код в общую переменную
        if_labels.append(("if", else_lbl, endif_lbl)) # сохраняем инфу о текущем if в стек
        continue

    elif secondSplit[0].startswith("}else"):
        # вышли из блока if и начинается else
        _, old_else, old_end = if_labels.pop() # вызов pop удаляем и передает последний элемент
        # достаем последнюю запись об if
        if_labels.append(("if-else", old_else, old_end))
        # обновляем тип 
        # генерим переход и метку else
        asm_code.append(f"    jmp {old_end}")
        asm_code.append(f"{old_else}:")
        continue

    elif secondSplit[0] == "while":
        cond_tokens = secondSplit[1:secondSplit.index(':')] # берем все что между while и :
        rpn = infix_to_postfix(cond_tokens) # переводим условие в обратную польскую запись
        # cond_tokens = ['x', '<', '10'] → rpn = ['x', '10', '<']
        *arith, operator = rpn # полученную запись передаем в arith, но последний элемент(оператор) передаем в op

        # создаем метки
        L = label_counter; label_counter += 1
        loop_lbl = f"Loop{L}"
        end_lbl  = f"EndLoop{L}"
        asm_code.append(f"{loop_lbl}:")
        asm_code.extend(rpn_to_masm(arith))
        # arith = ['x', '10'] → push DWORD PTR [x] → push 10
        asm_code += [
            "    pop ebx",
            "    pop eax",
            "    cmp eax, ebx",
            {
                '<':'jge', '<=':'jg',
                '>':'jle', '>=':'jl',
                '==':'jne', '!=':'je'
            }[operator] + f" {end_lbl}"
        ]
        if_labels.append(("while", loop_lbl, end_lbl)) # сохраняем инфу в стек 
        continue

    elif secondSplit[0] == "}":
        # если строка начинается с { значит мы вышли из блока
        if len(if_labels) < 0: # если нету блоков то пропускаем
            continue
        type, start, end = if_labels.pop() # берем инфу о последнем блоке и удаляем из стека
        if type == "while":
            asm_code.append(f"    jmp   {start}") # добавляем переход в начало цикла и метку окончания
            asm_code.append(f"{end}:")
        elif type == "if":
            asm_code.append(f"{end}:") # добавляем метку конца if
        else:
            asm_code.append(f"{end}:") # добавляем метку конца блока if-else
        continue
            
    else: # обработка команд присваивания
        if (len(secondSplit) < 3):   # если пустая то скип
            continue
        elif (secondSplit[1] == "="):
            readiSentence = infix_to_postfix(secondSplit[2:]) # преобразуем в обратную польскую все что после знака =
            masmCode = rpn_to_masm(readiSentence) # преобразованную часть переделываем в asm
            asm_code.extend(masmCode) # добавляем новый код ко всему
            
            ensure_variable(secondSplit[0])
            # проверяем, объявлена ли переменная с именем name в секции .data,
            # и если нет — добавляем её в vars_declared и в asm_data.

            asm_code.append("    pop eax") # забираем в eax результат из стека и сохраняем в этой переменной(которая до знака равно)
            asm_code.append(f"    mov [{secondSplit[0]}], eax")
            asm_code.append("") # для красоты для кайфа

# Запись полученного ассемблерного кода
with open("out.asm","w") as f: # открываем файл для записи
    f.write("""INCLUDE Irvine32.inc

.data\n""")
    f.write("\n".join(asm_data)) # объявления переменных
    f.write("""
.code
main PROC\n""") # секция кода и начало main
    f.write("\n".join(asm_code)) # сгенерированный код
    f.write("""
exit\t 
main ENDP
END main
""")
