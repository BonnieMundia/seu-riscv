// hello.c - Phase 1 smoke test: write 0xC0FFEE to the output port.
#define OUT_PORT (*(volatile unsigned *)0x10000000)

int main(void)
{
    OUT_PORT = 0x1234;
    OUT_PORT = 0xC0FFEE;
    return 0;
}
