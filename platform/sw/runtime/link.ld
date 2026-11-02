/* link.ld - place everything in the 64 KB RAM, starting at address 0 (reset PC). */
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY { RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 64K }

SECTIONS
{
    .text : {
        KEEP(*(.text.start))   /* crt0 must be first: the CPU starts at 0 */
        *(.text .text.*)
    } > RAM
    .rodata : { *(.rodata .rodata.* .srodata .srodata.*) } > RAM
    .data   : { *(.data .data.* .sdata .sdata.*) } > RAM
    .bss (NOLOAD) : ALIGN(4) {
        __bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > RAM
    _end = .;
}
