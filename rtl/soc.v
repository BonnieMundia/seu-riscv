// soc.v - minimal SoC: PicoRV32 (plain RV32I) + 64 KB RAM + output/done ports.
//
// Memory map (see docs/decisions.md):
//   0x0000_0000 - 0x0000_FFFF  64 KB RAM (program + stack)
//   0x1000_0000                output port (each write is logged as a result)
//   0x1000_0004                done port   (any write ends the run)
//
// Memory handshake (PicoRV32 native interface, README "Native Memory Interface"):
// the core raises mem_valid and holds addr/wdata/wstrb stable until we raise
// mem_ready for one cycle. We answer every request one cycle later, with the read
// data registered so it is valid in the same cycle mem_ready is high.

module soc #(
    parameter MEM_WORDS = 16384               // 64 KB as 32-bit words
) (
    input             clk,
    input             resetn,
    output            trap,
    output reg [31:0] out_data,
    output reg        out_valid,
    output reg        done,
    output reg        bad_addr              // access outside the memory map (debug aid)
);
    wire        mem_valid, mem_instr;
    reg         mem_ready;
    wire [31:0] mem_addr, mem_wdata;
    wire [ 3:0] mem_wstrb;
    reg  [31:0] mem_rdata;

    picorv32 #(
        .ENABLE_COUNTERS (1),
        .ENABLE_COUNTERS64(1),
        .ENABLE_REGS_16_31(1),
        .ENABLE_REGS_DUALPORT(1),
        .LATCHED_MEM_RDATA(0),
        .TWO_STAGE_SHIFT (1),
        .BARREL_SHIFTER  (0),
        .TWO_CYCLE_COMPARE(0),
        .TWO_CYCLE_ALU   (0),
        .COMPRESSED_ISA  (0),
        .CATCH_MISALIGN  (1),
        .CATCH_ILLINSN   (1),
        .ENABLE_PCPI     (0),
        .ENABLE_MUL      (0),
        .ENABLE_FAST_MUL (0),
        .ENABLE_DIV      (0),
        .ENABLE_IRQ      (0),
        .ENABLE_TRACE    (0),
        .REGS_INIT_ZERO  (0),
        .PROGADDR_RESET  (32'h0000_0000),
        .STACKADDR       (32'h0001_0000)
    ) cpu (
        .clk       (clk),
        .resetn    (resetn),
        .trap      (trap),
        .mem_valid (mem_valid),
        .mem_instr (mem_instr),
        .mem_ready (mem_ready),
        .mem_addr  (mem_addr),
        .mem_wdata (mem_wdata),
        .mem_wstrb (mem_wstrb),
        .mem_rdata (mem_rdata),
        // Unused features: inputs tied to 0 so simulation and synthesis agree.
        .pcpi_wr   (1'b0),
        .pcpi_rd   (32'h0),
        .pcpi_wait (1'b0),
        .pcpi_ready(1'b0),
        .irq       (32'h0),
        // Unused outputs, deliberately left unconnected.
        .mem_la_read(), .mem_la_write(), .mem_la_addr(), .mem_la_wdata(),
        .mem_la_wstrb(), .pcpi_valid(), .pcpi_insn(), .pcpi_rs1(), .pcpi_rs2(),
        .eoi(), .trace_valid(), .trace_data()
    );

    // RAM. Assumed ECC-protected in this study, so it is never a fault target.
    reg [31:0] ram [0:MEM_WORDS-1];

    // Program image: pass +hex=<file> at run time (default: program.hex).
    // Format: objcopy -O verilog --verilog-data-width=4 (word addresses, one
    // 32-bit word per entry) - see docs/decisions.md.
    reg [8*256-1:0] hexfile;
    initial begin
        if (!$value$plusargs("hex=%s", hexfile))
            hexfile = "program.hex";
        $readmemh(hexfile, ram);
    end

    wire        in_ram = (mem_addr < 4*MEM_WORDS);
    wire [13:0] widx   = mem_addr[15:2];

    always @(posedge clk) begin
        if (!resetn) begin
            mem_ready <= 0;
            mem_rdata <= 0;
            out_data  <= 0;
            out_valid <= 0;
            done      <= 0;
            bad_addr  <= 0;
        end else begin
            mem_ready <= 0;
            out_valid <= 0;
            if (mem_valid && !mem_ready) begin
                mem_ready <= 1;
                mem_rdata <= 32'h0;
                if (in_ram) begin
                    mem_rdata <= ram[widx];
                    if (mem_wstrb[0]) ram[widx][ 7: 0] <= mem_wdata[ 7: 0];
                    if (mem_wstrb[1]) ram[widx][15: 8] <= mem_wdata[15: 8];
                    if (mem_wstrb[2]) ram[widx][23:16] <= mem_wdata[23:16];
                    if (mem_wstrb[3]) ram[widx][31:24] <= mem_wdata[31:24];
                end else if (mem_addr == 32'h1000_0000 && |mem_wstrb) begin
                    out_data  <= mem_wdata;
                    out_valid <= 1;
                end else if (mem_addr == 32'h1000_0004 && |mem_wstrb) begin
                    done <= 1;
                end else begin
                    bad_addr <= 1;            // unmapped read/write: reads return 0
                end
            end
        end
    end
endmodule
