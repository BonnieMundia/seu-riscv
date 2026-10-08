// tb_soc.v - testbench for soc.v.
//
// Run-time options (plusargs):
//   +hex=<file>        program image (default program.hex)
//   +max_cycles=<n>    timeout; reports HANG if reached (default 1000000)
//   +vcd               dump waves to tb_soc.vcd (needs a build with --trace)
//
// Output lines (parsed later by Python tools):
//   OUT <hex value>            every write to the output port
//   DONE|TRAP|HANG cycles=<n>  how the run ended; n = clock cycles after reset release

`timescale 1ns/1ps

module tb_soc;
    reg clk = 0;
    reg resetn = 0;
    always #5 clk = ~clk;                       // 100 MHz nominal (time unit only)

    wire        trap, out_valid, done, bad_addr;
    wire [31:0] out_data;

    soc dut (
        .clk(clk), .resetn(resetn), .trap(trap),
        .out_data(out_data), .out_valid(out_valid), .done(done), .bad_addr(bad_addr)
    );

    integer max_cycles;
    integer cycles = 0;
    reg     warned = 0;

    initial begin
        if (!$value$plusargs("max_cycles=%d", max_cycles))
            max_cycles = 1000000;
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_soc.vcd");
            $dumpvars(0, tb_soc);
        end
        repeat (5) @(posedge clk);              // hold reset low for 5 cycles
        resetn <= 1;
    end

    always @(posedge clk) begin
        if (resetn) begin
            cycles <= cycles + 1;

            if (out_valid)
                $display("OUT %08x", out_data);

            if (bad_addr && !warned) begin      // bad_addr is sticky: report once
                $display("WARN bad_addr cycles=%0d", cycles);
                warned <= 1;
            end

            if (done) begin
                $display("DONE cycles=%0d", cycles);
                $finish;
            end else if (trap) begin
                $display("TRAP cycles=%0d", cycles);
                $finish;
            end else if (cycles >= max_cycles) begin
                $display("HANG cycles=%0d", cycles);
                $finish;
            end
        end
    end
endmodule
