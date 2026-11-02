// inject.cpp - Verilator fault-injection harness: one run = at most one bit flip.
//
// Runs the SoC exactly like tb_soc.v (5 reset cycles, same cycle count), but from
// C++, so it can stop the clock at cycle T and overwrite a flip-flop through VPI
// (the standard Verilog Procedural Interface; Verilator built with --vpi
// --public-flat-rw makes every signal reachable by its hierarchical name).
//
// Plusargs:
//   +hex=<file>          program image (read by soc.v's $readmemh)
//   +max_cycles=<n>      stop with status "hang" after n cycles (default 1000000)
//   +sig=<name>          signal to flip, Yosys-style name: cpu.reg_pc, cpu.cpuregs[5]
//   +bits=<b>[,<b>...]   bit(s) to flip together (one flip-flop may hold several bits)
//   +cycle=<t>           flip after t clock cycles (same count as tb_soc's cycles=)
//   +resolve=<file>      do not simulate: check that every name in <file> (one per
//                        line) can be found, print its width or "missing"
// Without +sig the run is fault-free (used to check against golden_runs.json).
//
// Output: one JSON line on stdout, e.g.
//   {"status":"done","cycles":147409,"outputs":["36c7bde8"],"bad_addr":false,
//    "injected":true,"before":"00000004","after":"00000005"}

#include "Vsoc.h"
#include "verilated.h"
#include "verilated_vpi.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

static const char *SCOPE = "TOP.soc.";       // Verilator's name for the top module

static std::string plusarg(const char *name) {
    const char *v = Verilated::commandArgsPlusMatch(name);  // returns "+name=value" or ""
    const char *eq = std::strchr(v, '=');
    return (v[0] && eq) ? std::string(eq + 1) : std::string();
}

// "cpu.cpuregs[5]" -> VPI handle of word 5 of the cpuregs memory; "cpu.reg_pc" -> reg.
static vpiHandle find(const std::string &name) {
    std::string base = name;
    int index = -1;
    size_t lb = name.find('[');
    if (lb != std::string::npos) {
        base = name.substr(0, lb);
        index = std::atoi(name.c_str() + lb + 1);
    }
    std::string full = SCOPE + base;
    vpiHandle h = vpi_handle_by_name(const_cast<PLI_BYTE8 *>(full.c_str()), nullptr);
    if (h && index >= 0) h = vpi_handle_by_index(h, index);
    return h;
}

static std::string hexvalue(vpiHandle h) {
    s_vpi_value v;
    v.format = vpiHexStrVal;
    vpi_get_value(h, &v);
    return v.value.str;
}

static void die(const std::string &msg) {
    std::printf("{\"status\":\"error\",\"error\":\"%s\"}\n", msg.c_str());
    std::exit(2);
}

// Flip the given bits of one signal. Returns false if a bit is out of range.
static bool flip(vpiHandle h, const std::vector<int> &bits) {
    int width = vpi_get(vpiSize, h);
    s_vpi_value v;
    v.format = vpiVectorVal;                 // value as 32-bit chunks: works for any width
    vpi_get_value(h, &v);
    std::vector<s_vpi_vecval> vec(v.value.vector, v.value.vector + (width + 31) / 32);
    for (int b : bits) {
        if (b < 0 || b >= width) return false;
        vec[b / 32].aval ^= (1u << (b % 32));
    }
    v.value.vector = vec.data();
    vpi_put_value(h, &v, nullptr, vpiNoDelay);
    return true;
}

static int resolve(const std::string &file) {
    std::ifstream in(file);
    if (!in) die("cannot open " + file);
    std::string name;
    int missing = 0;
    std::printf("{");
    for (bool first = true; std::getline(in, name); first = false) {
        vpiHandle h = find(name);
        if (h) std::printf("%s\"%s\":%d", first ? "" : ",", name.c_str(), (int)vpi_get(vpiSize, h));
        else { std::printf("%s\"%s\":\"missing\"", first ? "" : ",", name.c_str()); missing++; }
    }
    std::printf("}\n");
    return missing ? 1 : 0;
}

int main(int argc, char **argv) {
    auto ctx = std::make_unique<VerilatedContext>();
    ctx->commandArgs(argc, argv);
    auto top = std::make_unique<Vsoc>(ctx.get());

    std::string res = plusarg("resolve");
    if (!res.empty()) {
        top->eval();                          // build the design so names exist
        return resolve(res);
    }

    std::string s = plusarg("max_cycles");
    long max_cycles = s.empty() ? 1000000 : std::atol(s.c_str());
    std::string sig = plusarg("sig");
    long inject_at = -1;
    std::vector<int> bits;
    vpiHandle target = nullptr;
    if (!sig.empty()) {
        target = find(sig);
        if (!target) die("signal not found: " + sig);
        std::string c = plusarg("cycle"), b = plusarg("bits");
        if (c.empty() || b.empty()) die("+sig needs +cycle and +bits");
        inject_at = std::atol(c.c_str());
        for (char *p = &b[0]; *p;) {
            bits.push_back(std::strtol(p, &p, 10));
            if (*p == ',') p++;
        }
    }

    // One clock period = falling edge + rising edge; the design reacts on the rising edge.
    auto tick = [&]() {
        top->clk = 0; top->eval(); ctx->timeInc(5);
        top->clk = 1; top->eval(); ctx->timeInc(5);
    };

    top->resetn = 0;
    for (int i = 0; i < 5; i++) tick();       // like tb_soc: 5 cycles in reset
    top->resetn = 1;

    std::vector<std::string> outputs;
    std::string status, before, after;
    bool injected = false;
    long cycles = 0;
    for (;;) {
        if (cycles == inject_at) {
            before = hexvalue(target);
            if (!flip(target, bits)) die("bit out of range for " + sig);
            top->eval();                      // let combinational logic see the new value
            after = hexvalue(target);
            injected = true;
        }
        // Same checks, in the same order, as tb_soc.v does at each rising edge.
        if (top->out_valid) {
            char buf[16];
            std::snprintf(buf, sizeof buf, "%08x", (unsigned)top->out_data);
            if (outputs.size() < 64) outputs.push_back(buf);   // cap runaway output loops
        }
        if (top->done) { status = "done"; break; }
        if (top->trap) { status = "trap"; break; }
        if (cycles >= max_cycles) { status = "hang"; break; }
        tick();
        cycles++;
    }

    std::printf("{\"status\":\"%s\",\"cycles\":%ld,\"outputs\":[", status.c_str(), cycles);
    for (size_t i = 0; i < outputs.size(); i++)
        std::printf("%s\"%s\"", i ? "," : "", outputs[i].c_str());
    std::printf("],\"bad_addr\":%s,\"injected\":%s",
                top->bad_addr ? "true" : "false", injected ? "true" : "false");
    if (injected)
        std::printf(",\"before\":\"%s\",\"after\":\"%s\"", before.c_str(), after.c_str());
    std::printf("}\n");
    top->final();
    return 0;
}
