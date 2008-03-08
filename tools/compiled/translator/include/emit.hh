/*********************************************************************
 *
 * Copyright (C) 2007,  Simon Kagstrom
 *
 * Filename:      emit.hh
 * Author:        Simon Kagstrom <simon.kagstrom@gmail.com>
 * Description:   Emitter
 *
 * $Id:$
 *
 ********************************************************************/
#ifndef __EMIT_HH__
#define __EMIT_HH__

#include <stdio.h>
#include <stdint.h>
#include <registerallocator.hh>

class Emit
{
public:
  Emit();

  void bc_comment(const char *what) { this->output("; "); this->write(what); }

  void bc_generic(const char *what, ...);

  void bc_generic_insn(const char *what) { this->writeIndent(what); }

  void bc_label(const char *what, ...);

  void bc_goto(uint32_t dst) { this->writeIndent("goto L_%x", dst); }

  void bc_goto(const char *where) { this->writeIndent("goto %s", where); }

  void bc_condbranch(const char *what, ...);

  void bc_pushconst(int32_t nr);

  void bc_pushconst_u(uint32_t nr);

  void bc_pushregister(MIPS_register_t reg);

  void bc_popregister(MIPS_register_t reg);

  void bc_pushindex(MIPS_register_t reg, int32_t extra);

  void bc_pushaddress(MIPS_register_t reg, int32_t extra);

  void bc_getstatic(const char *what) { this->writeIndent("getstatic %s", what); }

  void bc_putstatic(const char *what) { this->writeIndent("putstatic %s", what); }

  void bc_iload(int n);

  void bc_istore(int n);

  void bc_ldc(char *str) { this->writeIndent("ldc \"%s\"", str); }

  void bc_iadd() { this->writeIndent("iadd"); }

  void bc_iinc(MIPS_register_t reg, int extra);

  void bc_isub() { this->writeIndent("isub"); }

  void bc_invokestatic(const char *what, ...);

  void bc_lookupswitch(int n, uint32_t *table, const char *def);

  void bc_iushr() { this->writeIndent("iushr"); }

  void bc_lushr() { this->writeIndent("lushr"); }

  void bc_imul() { this->writeIndent("imul"); }

  void bc_idiv() { this->writeIndent("idiv"); }

  void bc_irem() { this->writeIndent("irem"); }

  void bc_ineg() { this->writeIndent("ineg"); }

  void bc_ior() { this->writeIndent("ior"); }

  void bc_ixor() { this->writeIndent("ixor"); }

  void bc_lmul() { this->writeIndent("lmul"); }

  void bc_dup() { this->writeIndent("dup"); }

  void bc_dup2() { this->writeIndent("dup2"); }

  void bc_pop() { this->writeIndent("pop"); }

  void bc_pop2() { this->writeIndent("pop2"); }

  void bc_i2l() { this->writeIndent("i2l"); }

  void bc_l2i() { this->writeIndent("l2i"); }

  void bc_swap() { this->writeIndent("swap"); }

  void bc_iaload() { this->writeIndent("iaload"); }

  void bc_iastore() { this->writeIndent("iastore"); }

  void bc_ireturn() { this->writeIndent("ireturn"); }

  void bc_return() { this->writeIndent("return"); }


  void error(const char *dst, ...);

  void warning(const char *dst, ...);

  void setOutputFile(FILE *fp);

private:
  void bc_load_store_helper(const char *type, int nr);

  void write(const char *dst, ...);

  void writeIndent(const char *dst, ...);

  void output(const char *what);

  FILE *fp;
};

extern Emit *emit;

#endif /* !__EMIT_HH__ */
