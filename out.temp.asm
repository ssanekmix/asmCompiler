INCLUDE c:\Users\Sanekmix\.vscode\extensions\istareatscreens.masm-runner-0.6.1\native\irvine\Irvine32.inc

.data
a dd ?
b dd ?
d dd ?
str0 BYTE "\",0
str1 BYTE "How are you today?",0Dh,0Ah,0
answer dd ?
str2 BYTE 0Dh,0Ah,0
str3 BYTE "flkajfl",0
str4 BYTE "jfjf",0
str5 BYTE "What is your age?",0Dh,0Ah,0
age dd ?
str6 BYTE 0Dh,0Ah,0
.code
main PROC
    push 10
    pop eax
    mov [a], eax

    push 5
    pop eax
    mov [b], eax

    push DWORD PTR [a]
    push DWORD PTR [b]
    pop ebx
    pop eax
    add eax, ebx
    push eax
    pop eax
    mov [d], eax

    push DWORD PTR [d]
    pop   eax
    call  WriteInt
    lea   edx, str0
    call  WriteString
    lea   edx, str1
    call  WriteString
    call ReadInt
    mov [answer], eax
Loop0:
    push DWORD PTR [b]
    push 0
    pop ebx
    pop eax
    cmp eax, ebx
jle EndLoop0
    push DWORD PTR [b]
    push 1
    pop ebx
    pop eax
    sub eax, ebx
    push eax
    pop eax
    mov [b], eax

    push DWORD PTR [b]
    pop   eax
    call  WriteInt
    lea   edx, str2
    call  WriteString
    jmp   Loop0
EndLoop0:
    push DWORD PTR [d]
    push 10
    pop ebx
    pop eax
    cmp eax, ebx
    jl MakeIf1
    jmp MisIfOrMakeElse1
MakeIf1:
    lea   edx, str3
    call  WriteString
    jmp MisElse1
MisIfOrMakeElse1:
    lea   edx, str4
    call  WriteString
MisElse1:
    ; � ����� ����� if/else �
    lea   edx, str5
    call  WriteString
    call ReadInt
    mov [age], eax
    push DWORD PTR [age]
    pop   eax
    call  WriteInt
    lea   edx, str6
    call  WriteString
exit	 
main ENDP
END main
