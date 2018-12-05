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
from cc_targets import ProtoLibrary


class GrpcProtoLibrary(ProtoLibrary, java_targets.JavaTargetMixIn):
    """A scons proto library target subclass.

    This class is derived from SconsProtoLibrary.

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
                          'grpc_proto_library',
                          srcs,
                          deps,
                          '',
                          [], [], [], optimize, [], [],
                          blade,
                          kwargs)

        grpc_config = configparse.blade_config.get_config('grpc_proto_library_config')

    def _check_proto_deps(self):
        """Only grpc_proto_library or gen_rule target is allowed as deps. """
        proto_config = configparse.blade_config.get_config('grpc_proto_library_config')
        protobuf_libs = var_to_list(proto_config['protobuf_libs'])
        protobuf_java_libs = var_to_list(proto_config['protobuf_java_libs'])
        protobuf_libs = [self._unify_dep(d) for d in protobuf_libs + protobuf_java_libs]
        for dkey in self.deps:
            if dkey in protobuf_libs:
                continue
            dep = self.target_database[dkey]
            if dep.type != 'grpc_proto_library' and dep.type != 'gen_rule':
                console.error_exit('%s: Invalid dep %s. Proto_library can '
                    'only depend on grpc_proto_library or gen_rule.' %
                    (self.fullname, dep.fullname))

    def _prepare_to_generate_rule(self):
        ProtoLibrary._prepare_to_generate_rule(self)
        self._check_proto_deps()

    def _proto_gen_files(self, src):
        """_proto_gen_files. """
        proto_name = src[:-6]
        return (self._target_file_path('%s.pb.cc' % proto_name),
                self._target_file_path('%s.pb.h' % proto_name))

    def _proto_gen_php_file(self, src):
        """Generate the php file name. """
        proto_name = src[:-6]
        return self._target_file_path('%s.pb.php' % proto_name)

    def _proto_gen_python_file(self, src):
        """Generate the python file name. """
        proto_name = src[:-6]
        return self._target_file_path('%s_pb2.py' % proto_name)

    def _proto_gen_descriptor_file(self, name):
        """Generate the descriptor file name. """
        return self._target_file_path('%s.descriptors.pb' % name)

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def _get_java_package_name(self, content):
        """Get the java package name from proto file if it is specified. """
        java_package_pattern = '^\s*option\s*java_package\s*=\s*["\']([\w.]+)'
        m = re.search(java_package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        package_pattern = '^\s*package\s+([\w.]+)'
        m = re.search(package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        return ''

    def _proto_java_gen_class_name(self, src, content):
        """Get generated java class name"""
        pattern = '^\s*option\s+java_outer_classname\s*=\s*[\'"](\w+)["\']'
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            return m.group(1)
        proto_name = src[:-6]
        base_name = os.path.basename(proto_name)
        return ''.join([p[0].upper() + p[1:] for p in base_name.split('_') if p])

    def _proto_java_gen_file(self, src):
        """Generate the java files name of the proto library. """
        f = open(self._source_file_path(src))
        content = f.read()
        f.close()
        package_dir = self._get_java_package_name(content).replace('.', '/')
        class_name = self._proto_java_gen_class_name(src, content)
        java_name = '%s.java' % class_name
        return package_dir, java_name

    def _proto_java_rules(self):
        """Generate scons rules for the java files from proto file. """
        env_name = self._env_name()
        java_srcs = []
        java_src_vars = []
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            package_dir, java_name = self._proto_java_gen_file(src)
            proto_java_src = self._target_file_path(
                    os.path.join(os.path.dirname(src), package_dir, java_name))
            java_srcs.append(proto_java_src)
            java_src_var = self._var_name_of(proto_java_src)
            self._write_rule('%s = %s.ProtoJava("%s", "%s")' % (
                    java_src_var, env_name, proto_java_src, src_path))
            java_src_vars.append(java_src_var)
            self.data['java_sources'] = (
                    proto_java_src,
                    os.path.join(self.build_path, self.path),
                    self.name)
            self.data['java_sources_explict_dependency'].append(proto_java_src)

        self._generate_java_versions()
        self._generate_java_source_encoding()
        dep_jar_vars, dep_jars = self._get_compile_deps()
        self._generate_java_classpath(dep_jar_vars, dep_jars)
        var_name = self._var_name('jar')
        self._generate_generated_java_jar(var_name, java_src_vars)
        self._generate_java_depends(var_name, dep_jar_vars, dep_jars, '', '')
        self._add_target_var('jar', var_name)

    def _proto_php_rules(self):
        """Generate php files. """
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            proto_php_src = self._proto_gen_php_file(src)
            self._write_rule('%s.ProtoPhp(["%s"], "%s")' % (
                    self._env_name(),
                    proto_php_src,
                    src_path))

    def _proto_python_rules(self):
        """Generate python files. """
        env_name = self._env_name()
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            proto_python_src = self._proto_gen_python_file(src)
            py_src_var = self._var_name_of(src, 'python')
            self._write_rule('%s = %s.ProtoPython(["%s"], "%s")' % (
                    py_src_var,
                    env_name,
                    proto_python_src,
                    src_path))
            self.data['python_vars'].append(py_src_var)
            self.data['python_sources'].append(proto_python_src)
        py_lib_var = self._var_name('python')
        self._write_rule('%s["BASE_DIR"] = "%s"' % (env_name, self.build_path))
        self._write_rule('%s["BUILD_DIR"] = "%s"' % (env_name, self.build_path))
        self._write_rule('%s = %s.PythonLibrary(["%s"], [%s])' % (
            py_lib_var, env_name,
            self._target_file_path() + '.pylib',
            ', '.join(self.data['python_vars'])))
        self.data['python_var'] = py_lib_var

    def _proto_descriptor_rules(self):
        """Generate descriptor files. """
        proto_srcs = [os.path.join(self.path, src) for src in self.srcs]
        proto_descriptor_file = self._proto_gen_descriptor_file(self.name)
        self._write_rule('%s.ProtoDescriptors("%s", %s)' % (
                self._env_name(), proto_descriptor_file, proto_srcs))

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
    grpc_proto_library_target = ProtoLibrary(name,
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
