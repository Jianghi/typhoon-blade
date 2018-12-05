# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define grpc_proto_library target
"""


import os
import re
import blade

import console
import configparse
import build_rules
import java_targets
from blade_util import var_to_list
from proto_library_target import ProtoLibrary


class GrpcProtoLibrary(ProtoLibrary, java_targets.JavaTargetMixIn):
    """A scons proto library target subclass.

    This class is derived from SconsCcTarget.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 optimize,
                 deprecated,
                 generate_descriptors,
                 source_encoding,
                 blade,
                 kwargs):
        """Init method.

        Init the proto target.

        """
        ProtoLibrary.__init__(self,
                          name,
                          srcs,
                          deps,
                          optimize,
                          deprecated,
                          generate_descriptors,
                          source_encoding,
                          blade,
                          kwargs)
        proto_config = configparse.blade_config.get_config('proto_library_config')
        if proto_config.has_key("grpc_libs"):
            self.data['exported_deps'] += self._unify_deps(var_to_list(proto_config["grpc_libs"]))
            self._add_hardcode_library(var_to_list(proto_config["grpc_libs"]))

    def _proto_gen_grpc_files(self, src):
        """_proto_gen_files. """
        proto_name = src[:-6]
        return (self._target_file_path('%s.grpc.pb.cc' % proto_name),
                self._target_file_path('%s.grpc.pb.h' % proto_name))
    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        # Build java source according to its option
        env_name = self._env_name()

        options = self.blade.get_options()
        direct_targets = self.blade.get_direct_targets()

        if (getattr(options, 'generate_java', False) or
            self.data.get('generate_java') or
            self.data.get('generate_scala')):
            self._proto_java_rules()

        if (getattr(options, 'generate_php', False) or
            self.data.get('generate_php')):
            self._proto_php_rules()

        if (getattr(options, 'generate_python', False) or
            self.data.get('generate_python')):
            self._proto_python_rules()

        if self.data['generate_descriptors']:
            self._proto_descriptor_rules()

        self._setup_cc_flags()
        sources = []
        obj_names = []
        for src in self.srcs:
            (proto_src, proto_hdr) = self._proto_gen_files(src)
            self._write_rule('%s.Proto(["%s", "%s"], "%s")' % (
                    env_name, proto_src, proto_hdr, os.path.join(self.path, src)))
            obj_name = "%s_object" % self._var_name_of(src)
            obj_names.append(obj_name)
            self._write_rule(
                '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                'source="%s")' % (obj_name,
                                  env_name,
                                  proto_src,
                                  proto_src))
            sources.append(proto_src)
            self._write_rule('%s.Append(CPPFLAGS="%s")' % (env_name, '-std=c++11'))
            (proto_src, proto_hdr) = self._proto_gen_grpc_files(src)
            self._write_rule('%s.GrpcProto(["%s", "%s"], "%s")' % (
                    env_name, proto_src, proto_hdr, os.path.join(self.path, src)))
            obj_name = "%s_grpc_object" % self._var_name_of(src)
            obj_names.append(obj_name)
            self._write_rule(
                '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                'source="%s")' % (obj_name,
                                  env_name,
                                  proto_src,
                                  proto_src))
            sources.append(proto_src)

        # *.o depends on *pb.cc
        self._write_rule('%s = [%s]' % (self._objs_name(), ','.join(obj_names)))
        self._write_rule('%s.Depends(%s, %s)' % (
                         env_name, self._objs_name(), sources))

        # pb.cc depends on other grpc_proto_library
        for dep_name in self.deps:
            dep = self.target_database[dep_name]
            if not dep._generate_header_files():
                continue
            dep_var_name = dep._var_name()
            self._write_rule('%s.Depends(%s, %s)' % (
                    env_name, sources, dep_var_name))

        self._cc_library()


def grpc_proto_library(name,
                  srcs=[],
                  deps=[],
                  optimize=[],
                  deprecated=False,
                  generate_descriptors=False,
                  source_encoding='iso-8859-1',
                  **kwargs):
    """grpc_proto_library target. """
    grpc_proto_library_target = GrpcProtoLibrary(name,
                                        srcs,
                                        deps,
                                        optimize,
                                        deprecated,
                                        generate_descriptors,
                                        source_encoding,
                                        blade.blade,
                                        kwargs)
    blade.blade.register_target(grpc_proto_library_target)


build_rules.register_function(grpc_proto_library)
