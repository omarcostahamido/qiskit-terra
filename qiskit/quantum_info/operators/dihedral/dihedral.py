# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
CNOTDihedral operator class.
"""
# pylint: disable = abstract-method
import itertools
import numpy as np

from qiskit.exceptions import QiskitError
from qiskit.quantum_info.operators.base_operator import BaseOperator
from qiskit.quantum_info.operators.operator import Operator
from qiskit.quantum_info.operators.pauli import Pauli
from qiskit.quantum_info.operators.scalar_op import ScalarOp
from qiskit.quantum_info.synthesis.cnotdihedral_decompose import decompose_cnotdihedral
from qiskit.quantum_info.operators.mixins import generate_apidocs, AdjointMixin
from qiskit.circuit import QuantumCircuit, Instruction
from .dihedral_circuits import _append_circuit
from .polynomial import SpecialPolynomial


class CNOTDihedral(BaseOperator, AdjointMixin):
    """An N-qubit operator from the CNOT-Dihedral group.

     The CNOT-Dihedral group is generated by the quantum gates,
     :class:`~qiskit.circuit.library.CXGate`, :class:`~qiskit.circuit.library.TGate`,
     and :class:`~qiskit.circuit.library.XGate`.

     **Representation**

     An :math:`N`-qubit CNOT-Dihedral operator is stored as an affine function and a
     phase polynomial, based on the convention in references [1, 2].

     The affine function consists of an :math:`N \\times N` invertible binary matrix,
     and an :math:`N` binary vector.

     The phase polynomial is a polynomial of degree at most 3,
     in :math:`N` variables, whose coefficients are in the ring Z_8 with 8 elements.

     .. jupyter-execute::

         from qiskit import QuantumCircuit
         from qiskit.quantum_info import CNOTDihedral

         circ = QuantumCircuit(3)
         circ.cx(0, 1)
         circ.x(2)
         circ.t(1)
         circ.t(1)
         circ.t(1)
         elem = CNOTDihedral(circ)

         # Print the CNOTDihedral element
         print(elem)

    **Circuit Conversion**

     CNOTDihedral operators can be initialized from circuits containing *only* the
     following gates: :class:`~qiskit.circuit.library.IGate`,
     :class:`~qiskit.circuit.library.XGate`, :class:`~qiskit.circuit.library.YGate`,
     :class:`~qiskit.circuit.library.ZGate`,
     :class:`~qiskit.circuit.library.TGate`, :class:`~qiskit.circuit.library.TdgGate`
     :class:`~qiskit.circuit.library.SGate`, :class:`~qiskit.circuit.library.SdgGate`,
     :class:`~qiskit.circuit.library.CXGate`, :class:`~qiskit.circuit.library.CZGate`,
     :class:`~qiskit.circuit.library.SwapGate`.
     They can be converted back into a :class:`~qiskit.circuit.QuantumCircuit`,
     or :class:`~qiskit.circuit.Gate` object using the :meth:`~CNOTDihedral.to_circuit`
     or :meth:`~CNOTDihderal.to_instruction` methods respectively. Note that this
     decomposition is not necessarily optimal in terms of number of gates
     if the number of qubits is more than two.

     CNOTDihedral operators can also be converted to
     :class:`~qiskit.quantum_info.Operator` objects using the
     :meth:`to_operator` method. This is done via decomposing to a circuit,
     and then simulating the circuit as a unitary operator.

     References:
         1. Shelly Garion and Andrew W. Cross, *Synthesis of CNOT-Dihedral circuits
            with optimal number of two qubit gates*, `Quantum 4(369), 2020
            <https://quantum-journal.org/papers/q-2020-12-07-369/>`_
         2. Andrew W. Cross, Easwar Magesan, Lev S. Bishop, John A. Smolin and Jay M. Gambetta,
            *Scalable randomised benchmarking of non-Clifford gates*,
            npj Quantum Inf 2, 16012 (2016).
    """

    def __init__(self, data=None, num_qubits=None, validate=True):
        """Initialize a CNOTDihedral operator object.

        Args:
            data (CNOTDihedral or QuantumCircuit or ~qiskit.circuit.Instruction):
                Optional, operator to initialize.
            num_qubits (int): Optional, initialize an empty CNOTDihedral operator.
            validate (bool): if True, validates the CNOTDihedral element.

        Raises:
            QiskitError: if the type is invalid.
            QiskitError: if validate=True and the CNOTDihedral element is invalid.
        """

        if num_qubits:
            # initialize n-qubit identity
            self._num_qubits = num_qubits
            # phase polynomial
            self.poly = SpecialPolynomial(self._num_qubits)
            # n x n invertible matrix over Z_2
            self.linear = np.eye(self._num_qubits, dtype=np.int8)
            # binary shift, n coefficients in Z_2
            self.shift = np.zeros(self._num_qubits, dtype=np.int8)

        # Initialize from another CNOTDihedral by sharing the underlying
        # poly, linear and shift
        elif isinstance(data, CNOTDihedral):
            self.linear = data.linear
            self.shift = data.shift
            self.poly = data.poly

        # Initialize from ScalarOp as N-qubit identity discarding any global phase
        elif isinstance(data, ScalarOp):
            if not data.is_unitary() or set(data._input_dims) != {2} or data.num_qubits is None:
                raise QiskitError("Can only initialize from N-qubit identity ScalarOp.")
            self._num_qubits = data.num_qubits
            # phase polynomial
            self.poly = SpecialPolynomial(self._num_qubits)
            # n x n invertible matrix over Z_2
            self.linear = np.eye(self._num_qubits, dtype=np.int8)
            # binary shift, n coefficients in Z_2
            self.shift = np.zeros(self._num_qubits, dtype=np.int8)

        # Initialize from a QuantumCircuit or Instruction object
        elif isinstance(data, (QuantumCircuit, Instruction)):
            self._num_qubits = data.num_qubits
            elem = self._from_circuit(data)
            self.poly = elem.poly
            self.linear = elem.linear
            self.shift = elem.shift

        elif isinstance(data, Pauli):
            self._num_qubits = data.num_qubits
            elem = self._from_circuit(data.to_instruction())
            self.poly = elem.poly
            self.linear = elem.linear
            self.shift = elem.shift

        else:
            raise QiskitError("Invalid input type for CNOTDihedral class.")

        # Initialize BaseOperator
        super().__init__(num_qubits=self._num_qubits)

        # Validate the CNOTDihedral element
        if validate and not self._is_valid():
            raise QiskitError("Invalid CNOTDihedral element.")

    def _z2matmul(self, left, right):
        """Compute product of two n x n z2 matrices."""
        prod = np.mod(np.dot(left, right), 2)
        return prod

    def _z2matvecmul(self, mat, vec):
        """Compute mat*vec of n x n z2 matrix and vector."""
        prod = np.mod(np.dot(mat, vec), 2)
        return prod

    def _dot(self, other):
        """Left multiplication self * other."""
        if self.num_qubits != other.num_qubits:
            raise QiskitError("Multiplication on different number of qubits.")
        result = CNOTDihedral(num_qubits=self.num_qubits)
        result.shift = [
            (x[0] + x[1]) % 2 for x in zip(self._z2matvecmul(self.linear, other.shift), self.shift)
        ]
        result.linear = self._z2matmul(self.linear, other.linear)
        # Compute x' = B1*x + c1 using the p_j identity
        new_vars = []
        for i in range(self.num_qubits):
            support = np.arange(self.num_qubits)[np.nonzero(other.linear[i])]
            poly = SpecialPolynomial(self.num_qubits)
            poly.set_pj(support)
            if other.shift[i] == 1:
                poly = -1 * poly
                poly.weight_0 = (poly.weight_0 + 1) % 8
            new_vars.append(poly)
        # p' = p1 + p2(x')
        result.poly = other.poly + self.poly.evaluate(new_vars)
        return result

    def _compose(self, other):
        """Right multiplication other * self."""
        if self.num_qubits != other.num_qubits:
            raise QiskitError("Multiplication on different number of qubits.")
        result = CNOTDihedral(num_qubits=self.num_qubits)
        result.shift = [
            (x[0] + x[1]) % 2 for x in zip(self._z2matvecmul(other.linear, self.shift), other.shift)
        ]
        result.linear = self._z2matmul(other.linear, self.linear)
        # Compute x' = B1*x + c1 using the p_j identity
        new_vars = []
        for i in range(self.num_qubits):
            support = np.arange(other.num_qubits)[np.nonzero(self.linear[i])]
            poly = SpecialPolynomial(self.num_qubits)
            poly.set_pj(support)
            if self.shift[i] == 1:
                poly = -1 * poly
                poly.weight_0 = (poly.weight_0 + 1) % 8
            new_vars.append(poly)
        # p' = p1 + p2(x')
        result.poly = self.poly + other.poly.evaluate(new_vars)
        return result

    def __eq__(self, other):
        """Test equality."""
        return (
            isinstance(other, CNOTDihedral)
            and self.poly == other.poly
            and (self.linear == other.linear).all()
            and (self.shift == other.shift).all()
        )

    def _append_cx(self, i, j):
        """Apply a CX gate to this element.
        Left multiply the element by CX(i, j).
        """

        if not 0 <= i < self.num_qubits or not 0 <= j < self.num_qubits:
            raise QiskitError("CX qubits are out of bounds.")
        self.linear[j] = (self.linear[i] + self.linear[j]) % 2
        self.shift[j] = (self.shift[i] + self.shift[j]) % 2

    def _append_phase(self, k, i):
        """Apply an k-th power of T to this element.
        Left multiply the element by T_i^k.
        """
        if not 0 <= i < self.num_qubits:
            raise QiskitError("phase qubit out of bounds.")
        # If the kth bit is flipped, conjugate this gate
        if self.shift[i] == 1:
            k = (7 * k) % 8
        # Take all subsets \alpha of the support of row i
        # of weight up to 3 and add k*(-2)**(|\alpha| - 1) mod 8
        # to the corresponding term.
        support = np.arange(self.num_qubits)[np.nonzero(self.linear[i])]
        subsets_2 = itertools.combinations(support, 2)
        subsets_3 = itertools.combinations(support, 3)
        for j in support:
            value = self.poly.get_term([j])
            self.poly.set_term([j], (value + k) % 8)
        for j in subsets_2:
            value = self.poly.get_term(list(j))
            self.poly.set_term(list(j), (value + -2 * k) % 8)
        for j in subsets_3:
            value = self.poly.get_term(list(j))
            self.poly.set_term(list(j), (value + 4 * k) % 8)

    def _append_x(self, i):
        """Apply X to this element.
        Left multiply the element by X(i).
        """
        if not 0 <= i < self.num_qubits:
            raise QiskitError("X qubit out of bounds.")
        self.shift[i] = (self.shift[i] + 1) % 2

    def __str__(self):
        """Return formatted string representation."""
        out = "phase polynomial = \n"
        out += str(self.poly)
        out += "\naffine function = \n"
        out += " ("
        for row in range(self.num_qubits):
            wrote = False
            for col in range(self.num_qubits):
                if self.linear[row][col] != 0:
                    if wrote:
                        out += " + x_" + str(col)
                    else:
                        out += "x_" + str(col)
                        wrote = True
            if self.shift[row] != 0:
                out += " + 1"
            if row != self.num_qubits - 1:
                out += ","
        out += ")\n"
        return out

    def to_circuit(self):
        """Return a QuantumCircuit implementing the CNOT-Dihedral element.

        Return:
            QuantumCircuit: a circuit implementation of the CNOTDihedral object.

        References:
            1. Shelly Garion and Andrew W. Cross, *Synthesis of CNOT-Dihedral circuits
               with optimal number of two qubit gates*, `Quantum 4(369), 2020
               <https://quantum-journal.org/papers/q-2020-12-07-369/>`_
            2. Andrew W. Cross, Easwar Magesan, Lev S. Bishop, John A. Smolin and Jay M. Gambetta,
               *Scalable randomised benchmarking of non-Clifford gates*,
               npj Quantum Inf 2, 16012 (2016).
        """
        return decompose_cnotdihedral(self)

    def to_instruction(self):
        """Return a Gate instruction implementing the CNOTDihedral object."""
        return self.to_circuit().to_gate()

    def _from_circuit(self, circuit):
        """Initialize from a QuantumCircuit or Instruction.

        Args:
            circuit (QuantumCircuit or ~qiskit.circuit.Instruction):
                instruction to initialize.
        Returns:
            CNOTDihedral: the CNOTDihedral object for the circuit.
        Raises:
            QiskitError: if the input instruction is not CNOTDihedral or contains
                         classical register instruction.
        """
        if not isinstance(circuit, (QuantumCircuit, Instruction)):
            raise QiskitError("Input must be a QuantumCircuit or Instruction")

        # Initialize an identity CNOTDihedral object
        elem = CNOTDihedral(num_qubits=self._num_qubits)
        _append_circuit(elem, circuit)
        return elem

    def __array__(self, dtype=None):
        if dtype:
            return np.asarray(self.to_matrix(), dtype=dtype)
        return self.to_matrix()

    def to_matrix(self):
        """Convert operator to Numpy matrix."""
        return self.to_operator().data

    def to_operator(self):
        """Convert to an Operator object."""
        return Operator(self.to_instruction())

    def compose(self, other, qargs=None, front=False):
        if qargs is not None:
            raise NotImplementedError("compose method does not support qargs.")
        if self.num_qubits != other.num_qubits:
            raise QiskitError("Incompatible dimension for composition")
        if front:
            other = self._dot(other)
        else:
            other = self._compose(other)
        other.poly.weight_0 = 0  # set global phase
        return other

    def _tensor(self, other, reverse=False):
        """Returns the tensor product operator."""

        if not isinstance(other, CNOTDihedral):
            raise QiskitError("Tensored element is not a CNOTDihderal object.")

        if reverse:
            elem0 = self
            elem1 = other
        else:
            elem0 = other
            elem1 = self

        result = CNOTDihedral(num_qubits=elem0.num_qubits + elem1.num_qubits)
        linear = np.block(
            [
                [elem0.linear, np.zeros((elem0.num_qubits, elem1.num_qubits), dtype=np.int8)],
                [np.zeros((elem1.num_qubits, elem0.num_qubits), dtype=np.int8), elem1.linear],
            ]
        )
        result.linear = linear
        shift = np.block([elem0.shift, elem1.shift])
        result.shift = shift

        for i in range(elem0.num_qubits):
            value = elem0.poly.get_term([i])
            result.poly.set_term([i], value)
            for j in range(i):
                value = elem0.poly.get_term([j, i])
                result.poly.set_term([j, i], value)
                for k in range(j):
                    value = elem0.poly.get_term([k, j, i])
                    result.poly.set_term([k, j, i], value)

        for i in range(elem1.num_qubits):
            value = elem1.poly.get_term([i])
            result.poly.set_term([i + elem0.num_qubits], value)
            for j in range(i):
                value = elem1.poly.get_term([j, i])
                result.poly.set_term([j + elem0.num_qubits, i + elem0.num_qubits], value)
                for k in range(j):
                    value = elem1.poly.get_term([k, j, i])
                    result.poly.set_term(
                        [k + elem0.num_qubits, j + elem0.num_qubits, i + elem0.num_qubits], value
                    )

        return result

    def tensor(self, other):
        return self._tensor(other, reverse=True)

    def expand(self, other):
        return self._tensor(other, reverse=False)

    def adjoint(self):
        circ = self.to_instruction()
        result = self._from_circuit(circ.inverse())
        return result

    def conjugate(self):
        circ = self.to_instruction()
        new_circ = QuantumCircuit(self.num_qubits)
        bit_indices = {bit: index for index, bit in enumerate(circ.definition.qubits)}
        for instr, qregs, _ in circ.definition:
            new_qubits = [bit_indices[tup] for tup in qregs]
            if instr.name == "p":
                params = 2 * np.pi - instr.params[0]
                instr.params[0] = params
                new_circ.append(instr, new_qubits)
            elif instr.name == "t":
                instr.name = "tdg"
                new_circ.append(instr, new_qubits)
            elif instr.name == "tdg":
                instr.name = "t"
                new_circ.append(instr, new_qubits)
            elif instr.name == "s":
                instr.name = "sdg"
                new_circ.append(instr, new_qubits)
            elif instr.name == "sdg":
                instr.name = "s"
                new_circ.append(instr, new_qubits)
            else:
                new_circ.append(instr, new_qubits)
        result = self._from_circuit(new_circ)
        return result

    def transpose(self):
        circ = self.to_instruction()
        result = self._from_circuit(circ.reverse_ops())
        return result

    def _is_valid(self):
        """Return True if input is a CNOTDihedral element."""

        if (
            self.poly.weight_0 != 0
            or len(self.poly.weight_1) != self.num_qubits
            or len(self.poly.weight_2) != int(self.num_qubits * (self.num_qubits - 1) / 2)
            or len(self.poly.weight_3)
            != int(self.num_qubits * (self.num_qubits - 1) * (self.num_qubits - 2) / 6)
        ):
            return False
        if (
            (self.linear).shape != (self.num_qubits, self.num_qubits)
            or len(self.shift) != self.num_qubits
            or not np.allclose((np.linalg.det(self.linear) % 2), 1)
        ):
            return False
        if (
            not (set(self.poly.weight_1.flatten())).issubset({0, 1, 2, 3, 4, 5, 6, 7})
            or not (set(self.poly.weight_2.flatten())).issubset({0, 2, 4, 6})
            or not (set(self.poly.weight_3.flatten())).issubset({0, 4})
        ):
            return False
        if not (set(self.shift.flatten())).issubset({0, 1}) or not (
            set(self.linear.flatten())
        ).issubset({0, 1}):
            return False
        return True


# Update docstrings for API docs
generate_apidocs(CNOTDihedral)